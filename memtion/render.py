"""Drawing helpers: meme panel, Unicode text, debug overlay."""

from __future__ import annotations

import unicodedata
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from memtion.detector import Observation

FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
)

BG = (24, 24, 28)
ACCENT = (80, 200, 255)


@lru_cache(maxsize=8)
def _font(size: int):
    try:
        from PIL import ImageFont
    except ImportError:
        return None
    for path in FONT_CANDIDATES:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return None


def _ascii(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def draw_text_centered(img: np.ndarray, text: str, center_y: int, size: int = 28, color=(255, 255, 255)) -> None:
    """Draw text centred horizontally; uses a TTF font (Vietnamese ok) when available."""
    font = _font(size)
    if font is not None:
        from PIL import Image, ImageDraw

        pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil)
        x0, y0, x1, y1 = draw.textbbox((0, 0), text, font=font)
        x = (img.shape[1] - (x1 - x0)) // 2 - x0
        y = center_y - (y1 - y0) // 2 - y0
        draw.text((x, y), text, font=font, fill=color[::-1])
        img[:] = cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)
        return
    text = _ascii(text)
    scale = size / 30
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 2)
    org = ((img.shape[1] - tw) // 2, center_y + th // 2)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, 2, cv2.LINE_AA)


def load_image(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"cannot read image {path}")
    return img


def fit(img: np.ndarray, width: int, height: int) -> np.ndarray:
    """Letterbox `img` into a width x height canvas."""
    h, w = img.shape[:2]
    s = min(width / w, height / h)
    nw, nh = max(1, int(w * s)), max(1, int(h * s))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)
    canvas = np.full((height, width, 3), BG, dtype=np.uint8)
    x, y = (width - nw) // 2, (height - nh) // 2
    canvas[y : y + nh, x : x + nw] = resized
    return canvas


class MemePanel:
    """Caches the rendered meme panel (image + caption) per meme id."""

    LABEL_H = 64

    def __init__(self, size: int):
        self.size = size
        self._cache: dict[tuple[str, int], np.ndarray] = {}

    def render(self, meme_id: str | None, image_path: Path | None, label: str) -> np.ndarray:
        key = (meme_id or "", self.size)
        if key not in self._cache:
            panel = np.full((self.size, self.size, 3), BG, dtype=np.uint8)
            body = self.size - self.LABEL_H
            if image_path is not None:
                panel[:body] = fit(load_image(image_path), self.size, body)
            draw_text_centered(panel, label, body + self.LABEL_H // 2, size=30)
            self._cache[key] = panel
        return self._cache[key]


FACE_DEBUG_POINTS = (1, 10, 152, 234, 454, 33, 263, 61, 291, 13, 14)
POSE_EDGES = ((11, 12), (11, 13), (13, 15), (12, 14), (14, 16), (11, 23), (12, 24), (23, 24))


def draw_landmarks(img: np.ndarray, obs: Observation) -> None:
    if obs.pose is not None:
        p = obs.pose
        for a, b in POSE_EDGES:
            if min(p[a, 2], p[b, 2]) > 0.3:
                cv2.line(img, tuple(map(int, p[a, :2])), tuple(map(int, p[b, :2])), (255, 180, 60), 2, cv2.LINE_AA)
    if obs.face is not None:
        for i in FACE_DEBUG_POINTS:
            cv2.circle(img, tuple(map(int, obs.face[i])), 2, (60, 255, 120), -1, cv2.LINE_AA)
    for hand in obs.hands:
        color = (60, 120, 255) if hand.source == "hand" else (200, 80, 255)
        pts = hand.landmarks if hand.landmarks is not None else hand.points
        for pt in pts:
            cv2.circle(img, tuple(map(int, pt)), 3, color, -1, cv2.LINE_AA)
        if hand.gesture not in ("None", ""):
            org = tuple(map(int, hand.center + np.array([10, -10])))
            cv2.putText(img, hand.gesture, org, cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)


def draw_debug(img: np.ndarray, ranking: list[tuple[str, float]], features: dict[str, float], fps: float) -> None:
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (250, img.shape[0]), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, img, 0.45, 0, dst=img)
    y = 18
    cv2.putText(img, f"{fps:4.1f} fps", (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, ACCENT, 1, cv2.LINE_AA)
    y += 20
    for meme_id, score in ranking[:6]:
        w = int(min(score, 1.3) / 1.3 * 110)
        cv2.rectangle(img, (130, y - 10), (130 + w, y), ACCENT, -1)
        cv2.putText(img, f"{meme_id[:14]} {score:.2f}", (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        y += 16
    y += 8
    for name, value in sorted(features.items(), key=lambda kv: -kv[1]):
        if value < 0.05 or y > img.shape[0] - 6:
            continue
        cv2.putText(img, f"{name}: {value:.2f}", (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 255, 200), 1)
        y += 14
