import math

import numpy as np
import pytest

from memtion.features import FEATURE_NAMES, Calibration, compute_features, head_angles, ramp
from tests.helpers import hand_at, observation


def test_ramp():
    assert ramp(0.0, 0.2, 0.6) == 0.0
    assert ramp(0.4, 0.2, 0.6) == pytest.approx(0.5)
    assert ramp(1.0, 0.2, 0.6) == 1.0
    assert ramp(0.0, 1.0, 0.0) == 1.0  # decreasing ramp


def test_all_features_present_and_bounded():
    feats, _ = compute_features(observation({"mouthSmileLeft": 0.9, "mouthSmileRight": 0.9}))
    assert set(feats) == set(FEATURE_NAMES)
    assert all(0.0 <= v <= 1.0 for v in feats.values())
    assert feats["smile"] == 1.0
    assert feats["hands_free"] == 1.0


def test_no_face_no_hands():
    feats, _ = compute_features(observation(with_face=False))
    assert feats["face"] == 0.0
    assert feats["smile"] == 0.0
    assert feats["hands_free"] == 1.0


def _rot_x(deg):
    a = math.radians(deg)
    m = np.eye(4)
    m[1, 1], m[1, 2], m[2, 1], m[2, 2] = math.cos(a), -math.sin(a), math.sin(a), math.cos(a)
    return m


def test_head_angles():
    assert head_angles(np.eye(4)) == pytest.approx((0.0, 0.0, 0.0), abs=1e-6)
    # Rotating the face normal (+z) towards +y (up) means chin up -> positive pitch.
    pitch, yaw, _ = head_angles(_rot_x(-20))
    assert pitch == pytest.approx(20.0, abs=1e-4)
    assert yaw == pytest.approx(0.0, abs=1e-4)


def test_head_up_feature_and_calibration():
    obs = observation()
    obs.face_matrix = _rot_x(-25).astype(np.float32)
    feats, _ = compute_features(obs)
    assert feats["head_up"] == 1.0
    # If that is the user's neutral posture, calibration cancels it.
    feats, _ = compute_features(obs, calibration=Calibration(pitch=25.0))
    assert feats["head_up"] == 0.0


@pytest.mark.parametrize(
    ("u", "v", "zone"),
    [
        (0.0, 0.62, "chin"),
        (0.0, 1.2, "neck"),
        (0.4, 0.15, "cheek"),
        (-0.85, 0.3, "side"),
        (0.0, -0.8, "head"),
        (0.0, 2.3, "front"),
        (0.3, -2.0, "above"),
    ],
)
def test_hand_zones(u, v, zone):
    feats, _ = compute_features(observation(hands=[hand_at(u, v)]))
    assert feats[f"hand_{zone}"] == 1.0
    assert feats[f"one_hand_{zone}"] == 1.0
    assert feats[f"both_hands_{zone}"] == 0.0


def test_both_hands_and_hands_free():
    feats, _ = compute_features(observation(hands=[hand_at(-0.6, -0.8), hand_at(0.6, -0.8)]))
    assert feats["both_hands_head"] == 1.0
    assert feats["one_hand_head"] == 0.0
    assert feats["hands_free"] == 0.0


def test_far_hand_is_not_in_any_zone():
    feats, _ = compute_features(observation(hands=[hand_at(4.0, 0.0)]))
    assert max(feats[f"hand_{z}"] for z in ("chin", "neck", "cheek", "side", "head", "front", "above")) == 0.0
    assert feats["hands_free"] == 1.0


def test_thumbs_up_gesture():
    feats, _ = compute_features(observation(hands=[hand_at(2.0, 1.0, gesture="Thumb_Up", gesture_score=0.9)]))
    assert feats["thumbs_up"] == 1.0


def test_arms_crossed_from_pose():
    pose = np.zeros((33, 3), dtype=np.float32)
    pose[:, 2] = 1.0
    pose[11, :2] = (400, 380)  # left shoulder (image right)
    pose[12, :2] = (240, 380)  # right shoulder (image left)
    pose[15, :2] = (270, 450)  # left wrist crossed over to the right side
    pose[16, :2] = (370, 450)  # right wrist crossed over to the left side
    feats, _ = compute_features(observation(pose=pose))
    assert feats["arms_crossed"] == 1.0
    pose[15, :2], pose[16, :2] = (430, 450), (210, 450)  # uncrossed
    feats, _ = compute_features(observation(pose=pose))
    assert feats["arms_crossed"] == 0.0


def _pose_person():
    pose = np.zeros((33, 3), dtype=np.float32)
    pose[:, 2] = 1.0
    pose[0, :2] = (320, 240)  # nose
    pose[7, :2], pose[8, :2] = (370, 235), (270, 235)  # ears
    pose[11, :2], pose[12, :2] = (420, 380), (220, 380)  # shoulders
    return pose


def test_no_face_ignores_hand_near_face_zones():
    # A pose-only detection (no face mesh) is often a false positive on drawings.
    hand_on_cheek = hand_at(0.4, 0.15)
    feats, _ = compute_features(observation(hands=[hand_on_cheek], with_face=False, pose=_pose_person()))
    assert feats["hand_cheek"] == 0.0
    assert feats["hand_side"] == 0.0
    assert feats["hands_free"] == 1.0


def test_no_face_still_detects_arms_raised():
    hands = [hand_at(-1.5, -2.5), hand_at(1.5, -2.5)]
    feats, _ = compute_features(observation(hands=hands, with_face=False, pose=_pose_person()))
    assert feats["both_hands_above"] == 1.0
