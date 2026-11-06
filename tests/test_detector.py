import numpy as np

from memtion.detector import merge_pose_hands


def _pose(wrist_vis):
    pose = np.zeros((33, 3), dtype=np.float32)
    pose[:, 2] = 1.0
    pose[15, :2], pose[16, :2] = (100, 100), (500, 100)
    pose[15, 2] = pose[16, 2] = wrist_vis
    return pose


def test_pose_wrists_become_hands_when_confident():
    assert len(merge_pose_hands([], _pose(0.9))) == 2


def test_low_confidence_pose_wrists_are_ignored():
    assert merge_pose_hands([], _pose(0.45)) == []
