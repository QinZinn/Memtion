from pathlib import Path

import pytest

from memtion.features import FEATURE_NAMES
from memtion.matcher import ConfigError, Meme, Settings, Smoother, load_config, rank

ROOT = Path(__file__).resolve().parent.parent


def feats(**kw):
    f = dict.fromkeys(FEATURE_NAMES, 0.0)
    f.update(kw)
    return f


def test_score_is_soft_and():
    m = Meme("laugh", Path("x"), when={"smile": 1.0, "mouth_open": 1.0})
    assert m.score(feats(smile=1.0, mouth_open=1.0)) == pytest.approx(1.0)
    assert m.score(feats(smile=1.0)) < 0.2
    assert m.score(feats()) < 0.05


def test_negation_and_priority():
    m = Meme("grin", Path("x"), when={"smile": 1.0}, not_={"mouth_open": 1.0}, priority=1.5)
    assert m.score(feats(smile=1.0)) == pytest.approx(1.5)
    assert m.score(feats(smile=1.0, mouth_open=1.0)) < 0.3


def test_rank_orders_best_first():
    memes = [
        Meme("a", Path("x"), when={"smile": 1.0}),
        Meme("b", Path("x"), when={"smile": 1.0, "mouth_open": 1.0}),
    ]
    assert rank(memes, feats(smile=1.0))[0][0] == "a"
    assert dict(rank(memes, feats(smile=1.0, mouth_open=1.0)))["b"] == pytest.approx(1.0)


def test_smoother_hold_and_fallback():
    s = Smoother(Settings(fallback="idle", min_score=0.5, smoothing=1.0, hold_frames=3))
    assert s.update({"a": 0.9, "idle": 0.0}) == "a"  # first frame picks immediately
    assert s.update({"a": 0.1, "b": 0.9}) == "a"  # b must hold for 3 frames
    assert s.update({"a": 0.1, "b": 0.9}) == "a"
    assert s.update({"a": 0.1, "b": 0.9}) == "b"
    for _ in range(3):
        current = s.update({"a": 0.1, "b": 0.1})
    assert current == "idle"


def test_bundled_config_covers_all_sample_memes():
    config = load_config(ROOT / "memes.toml")
    files = {m.file.name for m in config.memes}
    samples = {p.name for p in (ROOT / "Sample_Meme").glob("*.jpg")}
    assert files == samples
    assert len(config.memes) == len(samples) == 20
    assert config.settings.fallback in {m.id for m in config.memes}


def test_config_rejects_unknown_feature(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"x")
    (tmp_path / "c.toml").write_text('[[meme]]\nid = "a"\nfile = "a.jpg"\nwhen = { smiel = 1.0 }\n')
    with pytest.raises(ConfigError, match="smiel"):
        load_config(tmp_path / "c.toml")
