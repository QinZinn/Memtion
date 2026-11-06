"""Command line entry point: `python -m memtion [options]`."""

from __future__ import annotations

import argparse
import contextlib
import os
import statistics
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from memtion.detector import Detector
from memtion.features import Calibration, compute_features, head_angles
from memtion.matcher import Config, ConfigError, Smoother, discover_packs, load_config, rank
from memtion.models import DEFAULT_MODEL_DIR, download_all
from memtion.paths import BUNDLED_PACKS, USER_PACKS, screenshot_dir
from memtion.render import MemePanel, draw_debug, draw_landmarks, draw_text_centered, load_image

WINDOW = "Memtion"
CALIBRATION_FRAMES = 20
TOAST_SECONDS = 2.0

HELP_KEYS = "q: thoát | p: đổi pack | d: debug | c: hiệu chỉnh mặt | l: chú thích | m: lật gương | s: chụp màn hình"


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="memtion", description="Hiện meme giống tư thế / biểu cảm của bạn qua webcam.")
    p.add_argument("--pack", help="pack bắt đầu (tên hoặc tên file, ví dụ: blob)")
    p.add_argument("--config", type=Path, help="chỉ dùng một file pack .toml cụ thể")
    p.add_argument("--camera", default="0", help="chỉ số webcam (0, 1, ...) hoặc đường dẫn file video")
    p.add_argument("--width", type=int, default=640, help="độ rộng khung hình camera yêu cầu")
    p.add_argument("--height", type=int, default=480, help="độ cao khung hình camera yêu cầu")
    p.add_argument("--fast", action="store_true", help="dùng pose model 'lite' (nhanh hơn, kém chính xác hơn)")
    p.add_argument("--debug", action="store_true", help="bật overlay debug ngay từ đầu")
    p.add_argument("--no-mirror", action="store_true", help="không lật ảnh camera như gương")
    p.add_argument("--labels", action="store_true", help="hiện dòng chú thích dưới meme (bật/tắt bằng phím l)")
    p.add_argument("--image", type=Path, help="phân tích một ảnh tĩnh thay vì webcam (in ra điểm số)")
    p.add_argument("--out", type=Path, help="với --image: lưu ảnh kết quả")
    p.add_argument("--models", type=Path, default=DEFAULT_MODEL_DIR, help="thư mục chứa model MediaPipe")
    p.add_argument("--download-models", action="store_true", help="chỉ tải model rồi thoát")
    p.add_argument("--list", action="store_true", help="liệt kê các pack và meme rồi thoát")
    return p.parse_args(argv)


def compose(frame: np.ndarray, panel: np.ndarray) -> np.ndarray:
    h = panel.shape[0]
    cam = cv2.resize(frame, (int(frame.shape[1] * h / frame.shape[0]), h))
    return np.hstack([cam, panel])


def run_image(args: argparse.Namespace, config: Config) -> int:
    frame = load_image(args.image)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    with Detector(args.models, video=False, pose_model="lite" if args.fast else "full") as det:
        obs = det.process(rgb)
    feats, raw = compute_features(obs, config.thresholds)
    ranking = rank(config.memes, feats)
    best_id, best_score = ranking[0]
    if best_score < config.settings.min_score and config.settings.fallback:
        best_id = config.settings.fallback

    print("Đặc trưng (> 0.05):")
    for k, v in sorted(feats.items(), key=lambda kv: -kv[1]):
        if v > 0.05:
            print(f"  {k:20s} {v:.2f}")
    print("Giá trị thô:", ", ".join(f"{k}={v:.2f}" for k, v in raw.items()))
    print("Xếp hạng meme:")
    for meme_id, score in ranking[:8]:
        print(f"  {meme_id:16s} {score:.3f}")
    print(f"=> {best_id}")

    if args.out:
        meme = config.by_id(best_id)
        panel = MemePanel(480, show_label=args.labels).render(meme.id, meme.file, meme.label)
        vis = frame.copy()
        draw_landmarks(vis, obs)
        cv2.imwrite(str(args.out), compose(vis, panel))
        print(f"Đã lưu {args.out}")
    return 0


def open_camera(source: str, width: int, height: int) -> cv2.VideoCapture:
    if source.isdigit():
        if sys.platform.startswith("linux"):
            backend = cv2.CAP_V4L2
        elif sys.platform == "win32":
            backend = cv2.CAP_DSHOW  # opens much faster than the default MSMF
        else:
            backend = cv2.CAP_AVFOUNDATION
        cap = cv2.VideoCapture(int(source), backend)
        if not cap.isOpened():
            cap = cv2.VideoCapture(int(source))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    else:
        cap = cv2.VideoCapture(source)
    return cap


def run_camera(args: argparse.Namespace, packs: list[Config], pack_index: int) -> int:
    if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        print("Không tìm thấy màn hình (DISPLAY/WAYLAND_DISPLAY). Hãy chạy trong phiên desktop.", file=sys.stderr)
        return 1
    cap = open_camera(args.camera, args.width, args.height)
    if not cap.isOpened():
        msg = f"Không mở được camera '{args.camera}'. Thử --camera 1, hoặc kiểm tra quyền truy cập camera."
        print(msg, file=sys.stderr)
        return 1

    is_file = not args.camera.isdigit()
    mirror = not args.no_mirror and not is_file
    debug = args.debug
    config = packs[pack_index]
    smoother = Smoother(config.settings)
    toast, toast_until = f"Pack: {config.name}", time.perf_counter() + TOAST_SECONDS
    calibration = Calibration()
    calibrating: list | None = None  # observations collected while calibrating
    panel = MemePanel(480, show_label=args.labels)
    fps, last = 0.0, time.perf_counter()
    start = time.perf_counter()
    last_ts = -1

    print(HELP_KEYS)
    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    with Detector(args.models, video=True, pose_model="lite" if args.fast else "full") as det:
        while True:
            ok, frame = cap.read()
            if not ok:
                if is_file:
                    break
                print("Mất tín hiệu camera.", file=sys.stderr)
                break
            if mirror:
                frame = cv2.flip(frame, 1)

            ts = int((time.perf_counter() - start) * 1000)
            ts = max(ts, last_ts + 1)  # MediaPipe needs strictly increasing timestamps
            last_ts = ts
            obs = det.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), ts)

            if calibrating is not None and obs.face is not None:
                calibrating.append(obs)
                if len(calibrating) >= CALIBRATION_FRAMES:
                    calibration = build_calibration(calibrating)
                    calibrating = None
                    smoother.reset()
                    print("Đã hiệu chỉnh khuôn mặt trung tính.")

            feats, _ = compute_features(obs, config.thresholds, calibration)
            ranking = rank(config.memes, feats)
            current = smoother.update(dict(ranking))

            now = time.perf_counter()
            fps = 0.9 * fps + 0.1 * (1.0 / max(now - last, 1e-6))
            last = now

            vis = frame.copy()
            if debug:
                draw_landmarks(vis, obs)
                draw_debug(vis, ranking, feats, fps)
            if calibrating is not None:
                draw_text_centered(vis, "Giữ mặt bình thường...", 40, size=26, color=(80, 200, 255))
            elif now < toast_until:
                draw_text_centered(vis, toast, 40, size=26, color=(80, 200, 255))
            if current is None:
                image = panel.render(None, None, "Không thấy ai cả")
            else:
                meme = config.by_id(current)
                image = panel.render(meme.id, meme.file, meme.label)
            out = compose(vis, image)
            cv2.imshow(WINDOW, out)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("d"):
                debug = not debug
            elif key == ord("l"):
                panel.show_label = not panel.show_label
            elif key == ord("m"):
                mirror = not mirror
            elif key == ord("p") and len(packs) > 1:
                pack_index = (pack_index + 1) % len(packs)
                config = packs[pack_index]
                smoother = Smoother(config.settings)
                toast, toast_until = f"Pack: {config.name}", time.perf_counter() + TOAST_SECONDS
                print(toast)
            elif key == ord("c"):
                calibrating = []
                calibration = Calibration()
            elif key == ord("s"):
                path = save_screenshot(out)
                print(f"Đã lưu {path}")
            if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                break
    cap.release()
    cv2.destroyAllWindows()
    return 0


def build_calibration(samples: list) -> Calibration:
    keys = set().union(*(s.blendshapes.keys() for s in samples))
    blend = {k: statistics.median(s.blendshapes.get(k, 0.0) for s in samples) for k in keys}
    angles = [head_angles(s.face_matrix) for s in samples if s.face_matrix is not None]
    if not angles:
        return Calibration(blendshapes=blend)
    pitch, yaw, roll = (statistics.median(a[i] for a in angles) for i in range(3))
    return Calibration(blendshapes=blend, pitch=pitch, yaw=yaw, roll=roll)


def save_screenshot(img: np.ndarray) -> Path:
    folder = screenshot_dir()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / time.strftime("memtion_%Y%m%d_%H%M%S.jpg")
    cv2.imwrite(str(path), img)
    return path


def load_packs(args: argparse.Namespace) -> tuple[list[Config], int]:
    """Packs to use and the index of the one to start with."""
    if args.config:
        return [load_config(args.config)], 0
    packs, errors = discover_packs(BUNDLED_PACKS)
    if USER_PACKS.is_dir():
        extra, extra_errors = discover_packs(USER_PACKS)
        packs += extra
        errors += extra_errors
    for err in errors:
        print(f"Bỏ qua pack lỗi: {err}", file=sys.stderr)
    if not packs:
        raise ConfigError(f"không tìm thấy pack nào trong {BUNDLED_PACKS}")
    if not args.pack:
        return packs, 0
    wanted = args.pack.lower()
    for i, pack in enumerate(packs):
        if wanted in (pack.name.lower(), pack.path.stem.lower() if pack.path else ""):
            return packs, i
    names = ", ".join(p.path.stem if p.path else p.name for p in packs)
    raise ConfigError(f"không có pack '{args.pack}'. Có: {names}")


def setup_console() -> None:
    """Make Vietnamese output work on consoles that default to a legacy code page (Windows)."""
    if sys.platform == "win32":
        import ctypes

        with contextlib.suppress(AttributeError, OSError):
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            with contextlib.suppress(OSError, ValueError):
                stream.reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    setup_console()
    args = parse_args(argv)
    if args.download_models:
        for path in download_all(args.models):
            print(path)
        return 0
    try:
        packs, start = load_packs(args)
    except (ConfigError, OSError) as exc:
        print(f"Lỗi cấu hình: {exc}", file=sys.stderr)
        return 2
    if args.list:
        for pack in packs:
            print(f"== {pack.name} ({pack.path.name if pack.path else ''}, {len(pack.memes)} meme)")
            for m in pack.memes:
                print(f"  {m.id:18s} {m.label}")
        print(f"Thêm pack riêng: đặt file .toml vào {USER_PACKS}")
        return 0
    if args.image:
        return run_image(args, packs[start])
    return run_camera(args, packs, start)
