"""Turn an `Observation` into named, normalised features in [0, 1].

Memes in `memes.toml` are described with these feature names, so this module
is the "vocabulary" of the app. Run the app with `--debug` to see live values.

Coordinates of hands are expressed in a *face frame*: origin at the nose tip,
`u` along the eye line in units of face width, `v` downwards in units of face
height. That makes "hand on chin", "hand by the ear", ... independent of how
far the user sits from the camera.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from memtion.detector import (
    POSE_HAND_GROUPS,
    POSE_L_EAR,
    POSE_L_SHOULDER,
    POSE_NOSE,
    POSE_R_EAR,
    POSE_R_SHOULDER,
    Hand,
    Observation,
)

# Face mesh landmark indices.
NOSE_TIP = 1
FOREHEAD = 10
CHIN = 152
CHEEK_R = 234  # subject's right (image left when not mirrored)
CHEEK_L = 454

# (low, high) for `ramp`: value <= low -> 0, value >= high -> 1.
# If low > high the ramp is decreasing. Can be overridden in memes.toml [thresholds].
DEFAULT_THRESHOLDS: dict[str, tuple[float, float]] = {
    "smile": (0.25, 0.65),
    "mouth_open": (0.12, 0.45),
    "eyes_closed": (0.35, 0.65),
    "eyes_wide": (0.15, 0.45),
    "squint": (0.3, 0.65),
    "brow_up": (0.25, 0.7),
    "brow_down": (0.2, 0.55),
    "frown": (0.08, 0.35),
    "pucker": (0.3, 0.7),
    "smirk": (0.12, 0.35),
    "grimace": (0.12, 0.4),
    "look_up": (0.15, 0.5),
    "head_up": (8.0, 22.0),  # degrees
    "head_down": (8.0, 22.0),  # degrees
    "head_turn": (14.0, 32.0),  # degrees
    "head_tilt": (9.0, 22.0),  # degrees
    "lean": (6.0, 16.0),  # degrees of shoulder line
    "thumbs_up": (0.4, 0.7),  # gesture recogniser score
    "zone": (1.6, 1.0),  # normalised ellipse distance -> membership
}

# Ellipses in the face frame: (centre_u, centre_v, radius_u, radius_v).
# Zones flagged symmetric use |u|, i.e. they exist on both sides of the face.
ZONES: dict[str, tuple[float, float, float, float, bool]] = {
    "chin": (0.0, 0.62, 0.45, 0.32, False),  # hand on / under the chin
    "neck": (0.0, 1.2, 0.7, 0.35, False),  # hands at the throat
    "cheek": (0.4, 0.15, 0.4, 0.4, True),  # hands covering cheeks / eyes
    "side": (0.8, 0.25, 0.4, 0.45, True),  # by the ear (phone call)
    "head": (0.0, -0.7, 1.1, 0.55, False),  # on top / sides of the head
    "front": (0.0, 2.3, 1.5, 0.9, False),  # in front of the chest (holding something)
}

FACE_FEATURES = (
    "face",
    "smile",
    "mouth_open",
    "eyes_closed",
    "eyes_wide",
    "squint",
    "eyes_shut",
    "brow_up",
    "brow_down",
    "frown",
    "pucker",
    "smirk",
    "grimace",
    "look_up",
    "head_up",
    "head_down",
    "head_turn",
    "head_tilt",
    "gaze_up",
)
HAND_ZONE_NAMES = (*ZONES, "above")
BODY_FEATURES = ("lean", "arms_crossed", "thumbs_up", "pointing", "hands_free", "hands_visible")


def _zone_feature_names() -> tuple[str, ...]:
    names = []
    for zone in HAND_ZONE_NAMES:
        names += [f"hand_{zone}", f"one_hand_{zone}", f"both_hands_{zone}"]
    return tuple(names)


FEATURE_NAMES: tuple[str, ...] = FACE_FEATURES + _zone_feature_names() + BODY_FEATURES


def ramp(x: float, low: float, high: float) -> float:
    if high == low:
        return 1.0 if x >= high else 0.0
    return float(min(1.0, max(0.0, (x - low) / (high - low))))


@dataclass
class Calibration:
    """Neutral-face baseline, subtracted from blendshapes and head angles."""

    blendshapes: dict[str, float] = field(default_factory=dict)
    pitch: float = 0.0
    yaw: float = 0.0
    roll: float = 0.0


@dataclass
class FaceFrame:
    origin: np.ndarray
    x_axis: np.ndarray
    y_axis: np.ndarray
    unit_u: float
    unit_v: float

    def to_face(self, p: np.ndarray) -> np.ndarray:
        d = np.atleast_2d(p) - self.origin
        return np.stack([d @ self.x_axis / self.unit_u, d @ self.y_axis / self.unit_v], axis=1)


def head_angles(matrix: np.ndarray) -> tuple[float, float, float]:
    """(pitch, yaw, roll) in degrees from MediaPipe's facial transformation matrix.

    pitch > 0: chin up / looking up. Yaw and roll are only used by magnitude.
    """
    r = np.asarray(matrix, dtype=np.float64)[:3, :3]
    forward = r[:, 2]  # face normal in camera space (y up)
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, forward[1]))))
    yaw = math.degrees(math.atan2(forward[0], forward[2]))
    roll = math.degrees(math.atan2(r[1, 0], r[0, 0]))
    return pitch, yaw, roll


def face_frame(obs: Observation) -> FaceFrame | None:
    if obs.face is not None:
        f = obs.face
        x_axis = f[CHEEK_L] - f[CHEEK_R]
        fw = float(np.linalg.norm(x_axis))
        fh = float(np.linalg.norm(f[CHIN] - f[FOREHEAD]))
        if fw < 1e-3 or fh < 1e-3:
            return None
        x_axis = x_axis / fw
        if x_axis[0] < 0:
            x_axis = -x_axis
        y_axis = np.array([-x_axis[1], x_axis[0]])
        # A turned head looks narrow; don't let that inflate |u|.
        return FaceFrame(f[NOSE_TIP], x_axis, y_axis, max(fw, 0.75 * fh), fh)
    if obs.pose is not None:
        p = obs.pose
        if min(p[POSE_NOSE, 2], p[POSE_L_EAR, 2], p[POSE_R_EAR, 2]) < 0.5:
            return None
        ear_w = float(np.linalg.norm(p[POSE_L_EAR, :2] - p[POSE_R_EAR, :2]))
        if ear_w < 1e-3:
            return None
        fw = ear_w * 0.95
        return FaceFrame(p[POSE_NOSE, :2], np.array([1.0, 0.0]), np.array([0.0, 1.0]), fw, fw * 1.25)
    return None


def zone_membership(uv: np.ndarray, zone: str, soft: tuple[float, float]) -> float:
    """Membership (0..1) of the best of several face-frame points in a zone."""
    if zone == "above":
        return ramp(float(-uv[:, 1].min()), 1.0, 1.5)
    cu, cv, ru, rv, symmetric = ZONES[zone]
    u = np.abs(uv[:, 0]) if symmetric else uv[:, 0]
    e = np.sqrt(((u - cu) / ru) ** 2 + ((uv[:, 1] - cv) / rv) ** 2)
    return ramp(float(e.min()), *soft)


def _finger_states(lm: np.ndarray) -> tuple[list[float], list[float]]:
    """Extended / curled degree for index, middle, ring, pinky."""
    ext, curl = [], []
    for tip, pip in ((8, 6), (12, 10), (16, 14), (20, 18)):
        r = np.linalg.norm(lm[tip] - lm[0]) / max(np.linalg.norm(lm[pip] - lm[0]), 1e-6)
        ext.append(ramp(r, 1.05, 1.3))
        curl.append(ramp(r, 1.1, 0.85))
    return ext, curl


def pointing_score(hand: Hand) -> float:
    if hand.landmarks is None:
        return 0.0
    if hand.gesture == "Pointing_Up":
        return max(hand.gesture_score, 0.0)
    ext, curl = _finger_states(hand.landmarks)
    return ext[0] * min(curl[1:]) * (0.0 if hand.gesture == "Thumb_Up" else 1.0)


def _top_two(values: list[float]) -> tuple[float, float]:
    s = sorted(values, reverse=True) + [0.0, 0.0]
    return s[0], s[1]


def compute_features(
    obs: Observation,
    thresholds: dict[str, tuple[float, float]] | None = None,
    calibration: Calibration | None = None,
) -> tuple[dict[str, float], dict[str, float]]:
    """Return (features in [0, 1], raw debug values)."""
    th = dict(DEFAULT_THRESHOLDS)
    if thresholds:
        th.update(thresholds)
    cal = calibration or Calibration()
    feats = dict.fromkeys(FEATURE_NAMES, 0.0)
    raw: dict[str, float] = {}

    # ---------------------------------------------------------------- face
    if obs.face is not None:
        feats["face"] = 1.0
        b = {k: max(0.0, v - cal.blendshapes.get(k, 0.0)) for k, v in obs.blendshapes.items()}

        def avg(*names: str) -> float:
            return sum(b.get(n, 0.0) for n in names) / len(names)

        smile_l, smile_r = b.get("mouthSmileLeft", 0.0), b.get("mouthSmileRight", 0.0)
        raw.update(
            smile=avg("mouthSmileLeft", "mouthSmileRight"),
            mouth_open=b.get("jawOpen", 0.0),
            eyes_closed=avg("eyeBlinkLeft", "eyeBlinkRight"),
            eyes_wide=avg("eyeWideLeft", "eyeWideRight"),
            squint=avg("eyeSquintLeft", "eyeSquintRight"),
            brow_up=b.get("browInnerUp", 0.0),
            brow_down=avg("browDownLeft", "browDownRight"),
            frown=avg("mouthFrownLeft", "mouthFrownRight"),
            pucker=max(b.get("mouthPucker", 0.0), b.get("mouthFunnel", 0.0)),
            smirk=abs(smile_l - smile_r),
            grimace=avg("mouthStretchLeft", "mouthStretchRight", "mouthUpperUpLeft", "mouthUpperUpRight"),
            look_up=avg("eyeLookUpLeft", "eyeLookUpRight"),
        )
        for name in (
            "smile", "mouth_open", "eyes_closed", "eyes_wide", "squint", "brow_up",
            "brow_down", "frown", "pucker", "grimace", "look_up",
        ):  # fmt: skip
            feats[name] = ramp(raw[name], *th[name])
        feats["smirk"] = ramp(raw["smirk"], *th["smirk"]) * ramp(max(smile_l, smile_r), 0.15, 0.4)

        if obs.face_matrix is not None:
            pitch, yaw, roll = head_angles(obs.face_matrix)
            pitch, yaw, roll = pitch - cal.pitch, yaw - cal.yaw, roll - cal.roll
            raw.update(pitch=pitch, yaw=yaw, roll=roll)
            feats["head_up"] = ramp(pitch, *th["head_up"])
            feats["head_down"] = ramp(-pitch, *th["head_down"])
            feats["head_turn"] = ramp(abs(yaw), *th["head_turn"])
            feats["head_tilt"] = ramp(abs(roll), *th["head_tilt"])
    feats["gaze_up"] = max(feats["look_up"], feats["head_up"])
    feats["eyes_shut"] = max(feats["eyes_closed"], feats["squint"])

    # ---------------------------------------------------------------- hands
    frame = face_frame(obs)
    feats["hands_visible"] = ramp(len(obs.hands), 0, 2)
    if frame is not None and obs.hands:
        # Without a face mesh the frame comes from the pose model, which also
        # "sees" people in drawings and clutter. Only trust it for arms raised
        # above the head (e.g. a backlit silhouette), not for hand-near-face zones.
        zones = HAND_ZONE_NAMES if obs.face is not None else ("above",)
        per_hand = []
        for hand in obs.hands:
            uv = frame.to_face(hand.points)
            per_hand.append({z: zone_membership(uv, z, th["zone"]) for z in zones})
        for zone in zones:
            first, second = _top_two([m[zone] for m in per_hand])
            feats[f"hand_{zone}"] = first
            feats[f"both_hands_{zone}"] = second
            feats[f"one_hand_{zone}"] = first * (1.0 - second)
        face_zones = [z for z in ("chin", "neck", "cheek", "side", "head") if z in zones]
        near_face = max((m[z] for m in per_hand for z in face_zones), default=0.0)
        feats["hands_free"] = 1.0 - near_face
    else:
        feats["hands_free"] = 1.0

    thumbs = [h.gesture_score for h in obs.hands if h.gesture == "Thumb_Up"]
    feats["thumbs_up"] = ramp(max(thumbs, default=0.0), *th["thumbs_up"])
    feats["pointing"] = max((pointing_score(h) for h in obs.hands), default=0.0)

    # ---------------------------------------------------------------- body
    p = obs.pose
    if p is not None and min(p[POSE_L_SHOULDER, 2], p[POSE_R_SHOULDER, 2]) > 0.5:
        ls, rs = p[POSE_L_SHOULDER, :2], p[POSE_R_SHOULDER, :2]
        d = ls - rs
        sw = max(float(np.linalg.norm(d)), 1e-6)
        angle = abs(math.degrees(math.atan2(d[1], d[0])))
        angle = min(angle, 180.0 - angle)
        raw["shoulder_angle"] = angle
        feats["lean"] = ramp(angle, *th["lean"])

        mid_x = (ls[0] + rs[0]) / 2
        (lw_i, *_), (rw_i, *_) = POSE_HAND_GROUPS
        if min(p[lw_i, 2], p[rw_i, 2]) > 0.3:
            # Left wrist on the right shoulder's side and vice versa, below the chin.
            l_cross = ramp((p[lw_i, 0] - mid_x) * np.sign(rs[0] - mid_x) / sw, -0.05, 0.2)
            r_cross = ramp((p[rw_i, 0] - mid_x) * np.sign(ls[0] - mid_x) / sw, -0.05, 0.2)
            below = 1.0
            if frame is not None:
                v = frame.to_face(p[[lw_i, rw_i], :2])[:, 1]
                below = ramp(float(v.min()), 0.5, 0.9)
            feats["arms_crossed"] = min(l_cross, r_cross) * below
    return feats, raw
