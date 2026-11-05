"""Command line entry point: `python -m memtion [options]`."""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from memtion.detector import Detector
from memtion.features import Calibration, compute_features, head_angles
from memtion.matcher import Config, ConfigError, Smoother, load_config, rank
from memtion.models import DEFAULT_MODEL_DIR, download_all
from memtion.render import MemePanel, draw_debug, draw_landmarks, draw_text_centered, load_image

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "memes.toml"
WINDOW = "Memtion"
CALIBRATION_FRAMES = 20

HELP_KEYS = "q: thoát | d: debug | c: hiệu chỉnh mặt | m: lật gương | s: chụp màn hình"


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="memtion", description="Hiện meme giống tư thế / biểu cảm của bạn qua webcam.")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="file cấu hình meme (mặc định: memes.toml)")
    p.add_argument("--camera", default="0", help="chỉ số webcam (0, 1, ...) hoặc đường dẫn file video")
    p.add_argument("--width", type=int, default=640, help="độ rộng khung hình camera yêu cầu")
    p.add_argument("--height", type=int, default=480, help="độ cao khung hình camera yêu cầu")
    p.add_argument("--fast", action="store_true", help="dùng pose model 'lite' (nhanh hơn, kém chính xác hơn)")
    p.add_argument("--debug", action="store_true", help="bật overlay debug ngay từ đầu")
    p.add_argument("--no-mirror", action="store_true", help="không lật ảnh camera như gương")
    p.add_argument("--image", type=Path, help="phân tích một ảnh tĩnh thay vì webcam (in ra điểm số)")
    p.add_argument("--out", type=Path, help="với --image: lưu ảnh kết quả")
    p.add_argument("--models", type=Path, default=DEFAULT_MODEL_DIR, help="thư mục chứa model MediaPipe")
    p.add_argument("--download-models", action="store_true", help="chỉ tải model rồi thoát")
    p.add_argument("--list", action="store_true", help="liệt kê các meme trong cấu hình rồi thoát")
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
        panel = MemePanel(480).render(meme.id, meme.file, meme.label)
        vis = frame.copy()
        draw_landmarks(vis, obs)
        cv2.imwrite(str(args.out), compose(vis, panel))
        print(f"Đã lưu {args.out}")
    return 0


def open_camera(source: str, width: int, height: int) -> cv2.VideoCapture:
    if source.isdigit():
        cap = cv2.VideoCapture(int(source), cv2.CAP_V4L2)
        if not cap.isOpened():
            cap = cv2.VideoCapture(int(source))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    else:
        cap = cv2.VideoCapture(source)
    return cap


def run_camera(args: argparse.Namespace, config: Config) -> int:
    if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        print("Không tìm thấy màn hình (DISPLAY/WAYLAND_DISPLAY). Hãy chạy trong phiên desktop.", file=sys.stderr)
        return 1
    cap = open_camera(args.camera, args.width, args.height)
    if not cap.isOpened():
        msg = f"Không mở được camera '{args.camera}'. Thử --camera 1, hoặc kiểm tra quyền /dev/video*."
        print(msg, file=sys.stderr)
        return 1

    is_file = not args.camera.isdigit()
    mirror = not args.no_mirror and not is_file
    debug = args.debug
    smoother = Smoother(config.settings)
    calibration = Calibration()
    calibrating: list | None = None  # observations collected while calibrating
    panel = MemePanel(480)
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
            elif key == ord("m"):
                mirror = not mirror
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
    folder = Path("screenshots")
    folder.mkdir(exist_ok=True)
    path = folder / time.strftime("memtion_%Y%m%d_%H%M%S.jpg")
    cv2.imwrite(str(path), img)
    return path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.download_models:
        for path in download_all(args.models):
            print(path)
        return 0
    try:
        config = load_config(args.config)
    except (ConfigError, OSError) as exc:
        print(f"Lỗi cấu hình: {exc}", file=sys.stderr)
        return 2
    if args.list:
        for m in config.memes:
            print(f"{m.id:16s} {m.label}  <- {m.file.name}")
        return 0
    if args.image:
        return run_image(args, config)
    return run_camera(args, config)
