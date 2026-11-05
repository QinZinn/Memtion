"""Download and locate the MediaPipe model files."""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

_BASE = "https://storage.googleapis.com/mediapipe-models"

MODELS = {
    "face": ("face_landmarker.task", f"{_BASE}/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"),
    "gesture": (
        "gesture_recognizer.task",
        f"{_BASE}/gesture_recognizer/gesture_recognizer/float16/latest/gesture_recognizer.task",
    ),
    "pose_lite": (
        "pose_landmarker_lite.task",
        f"{_BASE}/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task",
    ),
    "pose_full": (
        "pose_landmarker_full.task",
        f"{_BASE}/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task",
    ),
}

DEFAULT_MODEL_DIR = Path(__file__).resolve().parent.parent / "models"


def ensure_model(key: str, model_dir: Path = DEFAULT_MODEL_DIR) -> Path:
    """Return the local path of a model, downloading it the first time."""
    filename, url = MODELS[key]
    path = Path(model_dir) / filename
    if path.exists() and path.stat().st_size > 0:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[memtion] Downloading {filename} ...", file=sys.stderr)
    tmp = path.with_suffix(".part")
    with urllib.request.urlopen(url, timeout=60) as resp, open(tmp, "wb") as out:
        while chunk := resp.read(1 << 16):
            out.write(chunk)
    tmp.replace(path)
    return path


def download_all(model_dir: Path = DEFAULT_MODEL_DIR) -> list[Path]:
    return [ensure_model(key, model_dir) for key in MODELS]
