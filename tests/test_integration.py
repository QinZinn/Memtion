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
def detector():
    from memtion.detector import Detector

    with Detector(video=False) as det:
        yield det


@pytest.mark.parametrize("meme_id", ["shocked", "choking", "phone_call", "break_free"])
def test_human_meme_matches_itself(detector, meme_id):
    from memtion.features import compute_features

    config = load_config(ROOT / "memes.toml")
    meme = config.by_id(meme_id)
    frame = cv2.cvtColor(cv2.imread(str(meme.file)), cv2.COLOR_BGR2RGB)
    feats, _ = compute_features(detector.process(frame), config.thresholds)
    assert rank(config.memes, feats)[0][0] == meme_id
