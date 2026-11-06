"""End-to-end check on the sample memes that show real people (needs MediaPipe + models)."""

from pathlib import Path

import pytest

from memtion.matcher import load_config, rank
from memtion.models import DEFAULT_MODEL_DIR, MODELS

ROOT = Path(__file__).resolve().parent.parent
pytest.importorskip("mediapipe")
cv2 = pytest.importorskip("cv2")

if not all((DEFAULT_MODEL_DIR / name).exists() for name, _ in MODELS.values()):
    pytest.skip("models not downloaded (python -m memtion --download-models)", allow_module_level=True)


@pytest.fixture(scope="module")
def image_detector():
    from memtion.detector import Detector

    with Detector(video=False) as det:
        yield det


def observe(image_detector, frame, mode):
    """IMAGE mode, or VIDEO mode (what the webcam loop uses: tracks across frames)."""
    if mode == "image":
        return image_detector.process(frame)
    from memtion.detector import Detector

    with Detector(video=True) as det:
        for i in range(10):  # a person holding the pose for a moment
            obs = det.process(frame, timestamp_ms=i * 66)
    return obs


def webcam_crop(img, w=640, h=480):
    """Centre-crop to 4:3 like a webcam frame (cuts off part of the head/arms)."""
    ih, iw = img.shape[:2]
    s = max(w / iw, h / ih)
    img = cv2.resize(img, (round(iw * s), round(ih * s)), interpolation=cv2.INTER_AREA)
    y, x = (img.shape[0] - h) // 2, (img.shape[1] - w) // 2
    return img[y : y + h, x : x + w]


@pytest.mark.parametrize("mode", ["image", "video"])
@pytest.mark.parametrize("framing", ["original", "webcam"])
@pytest.mark.parametrize("meme_id", ["shocked", "choking", "phone_call", "break_free"])
def test_human_meme_matches_itself(image_detector, meme_id, framing, mode):
    from memtion.features import compute_features

    config = load_config(ROOT / "packs" / "default.toml")
    meme = config.by_id(meme_id)
    frame = cv2.cvtColor(cv2.imread(str(meme.file)), cv2.COLOR_BGR2RGB)
    if framing == "webcam":
        frame = webcam_crop(frame)
    feats, _ = compute_features(observe(image_detector, frame, mode), config.thresholds)
    assert rank(config.memes, feats)[0][0] == meme_id
