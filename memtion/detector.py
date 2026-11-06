"""Thin wrapper around MediaPipe (face, pose, hands) producing an `Observation`.

Everything downstream (features, matching) only works with the plain numpy
data in `Observation`, so it can be unit-tested without MediaPipe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Self

import numpy as np

from memtion.models import DEFAULT_MODEL_DIR, ensure_model

# Pose landmark indices (MediaPipe BlazePose, 33 points).
POSE_NOSE = 0
POSE_L_EAR, POSE_R_EAR = 7, 8
POSE_L_SHOULDER, POSE_R_SHOULDER = 11, 12
POSE_L_ELBOW, POSE_R_ELBOW = 13, 14
POSE_L_WRIST, POSE_R_WRIST = 15, 16
# wrist, pinky, index, thumb for each side
POSE_HAND_GROUPS = ((15, 17, 19, 21), (16, 18, 20, 22))

# Hand landmark indices used for the palm centre and fingertips.
PALM = (0, 5, 9, 13, 17)
FINGERTIPS = (4, 8, 12, 16, 20)


@dataclass
class Hand:
    center: np.ndarray  # (2,) pixels
    points: np.ndarray  # (N, 2) pixels - centre + fingertips (or pose wrist group)
    landmarks: np.ndarray | None = None  # (21, 2) pixels when found by the hand model
    gesture: str = "None"
    gesture_score: float = 0.0
    source: str = "hand"  # "hand" (hand model) or "pose" (pose wrist fallback)


@dataclass
class Observation:
    width: int
    height: int
    face: np.ndarray | None = None  # (478, 2) pixels
    blendshapes: dict[str, float] = field(default_factory=dict)
    face_matrix: np.ndarray | None = None  # (4, 4) facial transformation matrix
    pose: np.ndarray | None = None  # (33, 3) pixels x, y + visibility
    hands: list[Hand] = field(default_factory=list)


def _to_px(landmarks, w: int, h: int) -> np.ndarray:
    return np.array([[lm.x * w, lm.y * h] for lm in landmarks], dtype=np.float32)


def merge_pose_hands(hands: list[Hand], pose: np.ndarray | None, min_visibility: float = 0.5) -> list[Hand]:
    """Add hands seen only by the pose model (e.g. a hand hidden behind the head).

    The hand model often misses hands that are partly occluded or out of frame,
    while the pose model still estimates the wrists.
    """
    merged = list(hands)
    if pose is None:
        return merged
    for group in POSE_HAND_GROUPS:
        if pose[group[0], 2] < min_visibility:
            continue
        pts = pose[list(group), :2]
        wrist = pts[0]
        duplicate = False
        for hand in hands:
            if hand.landmarks is None:
                continue
            size = float(np.linalg.norm(hand.landmarks[0] - hand.landmarks[9])) or 1.0
            if np.linalg.norm(hand.landmarks[0] - wrist) < 2.0 * size:
                duplicate = True
                break
        if not duplicate:
            merged.append(Hand(center=pts.mean(axis=0), points=pts, source="pose"))
    return merged


class Detector:
    """Runs the face landmarker, pose landmarker and gesture recognizer."""

    def __init__(self, model_dir: Path = DEFAULT_MODEL_DIR, video: bool = True, pose_model: str = "full"):
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision

        self._mp = mp
        mode = vision.RunningMode.VIDEO if video else vision.RunningMode.IMAGE
        self.video = video

        def base(key: str) -> BaseOptions:
            return BaseOptions(model_asset_path=str(ensure_model(key, model_dir)))

        self.face = vision.FaceLandmarker.create_from_options(
            vision.FaceLandmarkerOptions(
                base_options=base("face"),
                running_mode=mode,
                num_faces=1,
                output_face_blendshapes=True,
                output_facial_transformation_matrixes=True,
            )
        )
        self.pose = vision.PoseLandmarker.create_from_options(
            vision.PoseLandmarkerOptions(
                base_options=base("pose_full" if pose_model == "full" else "pose_lite"),
                running_mode=mode,
                num_poses=1,
            )
        )
        self.gesture = vision.GestureRecognizer.create_from_options(
            vision.GestureRecognizerOptions(base_options=base("gesture"), running_mode=mode, num_hands=2)
        )

    def process(self, frame_rgb: np.ndarray, timestamp_ms: int = 0) -> Observation:
        """Analyse one RGB frame (H, W, 3 uint8)."""
        h, w = frame_rgb.shape[:2]
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(frame_rgb))
        if self.video:
            face_res = self.face.detect_for_video(image, timestamp_ms)
            pose_res = self.pose.detect_for_video(image, timestamp_ms)
            hand_res = self.gesture.recognize_for_video(image, timestamp_ms)
        else:
            face_res = self.face.detect(image)
            pose_res = self.pose.detect(image)
            hand_res = self.gesture.recognize(image)

        obs = Observation(width=w, height=h)
        if face_res.face_landmarks:
            obs.face = _to_px(face_res.face_landmarks[0], w, h)
            if face_res.face_blendshapes:
                obs.blendshapes = {c.category_name: float(c.score) for c in face_res.face_blendshapes[0]}
            if face_res.facial_transformation_matrixes:
                obs.face_matrix = np.asarray(face_res.facial_transformation_matrixes[0], dtype=np.float32)

        if pose_res.pose_landmarks:
            lms = pose_res.pose_landmarks[0]
            obs.pose = np.array(
                [[lm.x * w, lm.y * h, lm.visibility if lm.visibility is not None else 1.0] for lm in lms],
                dtype=np.float32,
            )

        hands: list[Hand] = []
        for i, lms in enumerate(hand_res.hand_landmarks or []):
            pts = _to_px(lms, w, h)
            gesture, score = "None", 0.0
            if hand_res.gestures and i < len(hand_res.gestures) and hand_res.gestures[i]:
                top = hand_res.gestures[i][0]
                gesture, score = top.category_name or "None", float(top.score)
            center = pts[list(PALM)].mean(axis=0)
            hands.append(
                Hand(
                    center=center,
                    points=np.vstack([center[None], pts[list(FINGERTIPS)]]),
                    landmarks=pts,
                    gesture=gesture,
                    gesture_score=score,
                )
            )
        obs.hands = merge_pose_hands(hands, obs.pose)
        return obs

    def close(self) -> None:
        for task in (self.face, self.pose, self.gesture):
            task.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc) -> None:
        self.close()
