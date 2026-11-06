"""Rule-conflict checks: a person doing each expression should get that meme.

Each scenario lists the features (0..1) such a person would produce; anything
not listed is 0, except `face` = 1 and `hands_free` = 1 unless overridden.
"""

from pathlib import Path

import pytest

from memtion.features import FEATURE_NAMES
from memtion.matcher import load_config, rank

ROOT = Path(__file__).resolve().parent.parent

BLOB = {
    "thumbs_down": dict(thumbs_down=1, hands_visible=0.5),
    "nerd": dict(thumbs_up=1, smile=0.6, hands_visible=0.5),
    "heart_hands": dict(hands_visible=1, smile=1, mouth_open=0.6, hand_chin=1, both_hands_chin=1, hands_free=0),
    "oxygen": dict(hand_chin=1, one_hand_chin=1, eyes_closed=1, eyes_shut=1, hands_free=0, hands_visible=0.5),
    "flowers": dict(hand_front=1, both_hands_front=1, smile=0.8, hands_visible=1),
    "laugh": dict(smile=1, mouth_open=1),
    "tongue_crazy": dict(smile=0.8, mouth_open=1, squint=1, eyes_shut=1),
    "crying_waterfall": dict(mouth_open=1, brow_up=1, eyes_closed=0.8, eyes_shut=0.8, frown=0.5),
    "horror": dict(mouth_open=1, brow_up=1, eyes_wide=1),
    "angry": dict(mouth_open=1, brow_down=1),
    "sweating": dict(eyes_closed=1, eyes_shut=1, mouth_open=0.8),
    "sad_open": dict(frown=1, mouth_open=0.7),
    "aaa": dict(mouth_open=1),
    "bleh": dict(head_tilt=1, mouth_open=0.6),
    "clown": dict(smile=1, eyes_wide=1),
    "squint_smile": dict(smile=1, squint=1, eyes_shut=1),
    "bliss": dict(eyes_closed=1, eyes_shut=1, smile=0.6),
    "shy": dict(smile=1, head_down=1),
    "cheeky": dict(smile=1, head_tilt=1),
    "sly": dict(smirk=1, smile=0.6, brow_down=0.5),
    "smile": dict(smile=1),
    "kiss": dict(pucker=1, eyes_closed=1, eyes_shut=1),
    "lips": dict(pucker=1),
    "puffed": dict(cheek_puff=1),
    "pout": dict(lips_pressed=1),
    "worried": dict(frown=1, brow_up=1),
    "disgust": dict(brow_down=1, frown=1),
    "serious": dict(brow_down=1),
    "working": dict(head_down=1),
    "deadpan": dict(),
}

DEFAULT = {
    "break_free": dict(hand_above=1, both_hands_above=1, hands_visible=1),
    "thumbs_up": dict(thumbs_up=1, smile=0.5, hands_visible=0.5),
    "shocked": dict(hand_head=1, both_hands_head=1, mouth_open=1, eyes_wide=1, brow_up=1, hands_free=0),
    "phone_call": dict(hand_side=1, one_hand_side=1, hands_free=0, hands_visible=0.5),
    "choking": dict(hand_neck=1, both_hands_neck=1, squint=1, eyes_shut=1, grimace=1, hands_free=0),
    "thinking_side": dict(hand_chin=1, one_hand_chin=1, head_turn=1, hands_free=0),
    # A fist under the chin also brushes the neck zone a little.
    "thinking": dict(hand_chin=1, one_hand_chin=1, hand_neck=0.45, gaze_up=1, hands_free=0),
    "laughing": dict(smile=1, mouth_open=1),
    "grin": dict(smile=1),
    "content": dict(eyes_closed=1, eyes_shut=1, head_up=1, gaze_up=1),
    "lone_wolf": dict(head_turn=1),
}


def features(**kw):
    f = dict.fromkeys(FEATURE_NAMES, 0.0)
    f.update(face=1.0, hands_free=1.0)
    f.update({k: float(v) for k, v in kw.items()})
    return f


MIN_MARGIN = 0.1  # the winner must lead clearly, not just by its position in the file


def winner(config, feats):
    (best, score), (_, second) = rank(config.memes, feats)[:2]
    if score < config.settings.min_score:
        return config.settings.fallback
    return best if score - second >= MIN_MARGIN else f"tie({best})"


@pytest.mark.parametrize(("pack", "scenarios"), [("blob", BLOB), ("default", DEFAULT)])
def test_each_expression_picks_its_meme(pack, scenarios):
    config = load_config(ROOT / "packs" / f"{pack}.toml")
    wrong = {}
    for meme_id, kw in scenarios.items():
        got = winner(config, features(**kw))
        if got != meme_id:
            wrong[meme_id] = got
    assert not wrong, f"expected -> got: {wrong}"


def test_blob_scenarios_cover_the_whole_pack():
    config = load_config(ROOT / "packs" / "blob.toml")
    assert set(BLOB) == {m.id for m in config.memes}
