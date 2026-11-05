import numpy as np

from memtion.detector import Hand, Observation
from memtion.features import CHEEK_L, CHEEK_R, CHIN, FOREHEAD, NOSE_TIP


def make_face(nose=(320.0, 240.0), width=100.0, height=130.0) -> np.ndarray:
    """A fake 478-point face mesh with only the landmarks the features use."""
    nx, ny = nose
    face = np.tile(np.array([nx, ny], dtype=np.float32), (478, 1))
    face[NOSE_TIP] = (nx, ny)
    face[CHEEK_R] = (nx - width / 2, ny)
    face[CHEEK_L] = (nx + width / 2, ny)
    face[FOREHEAD] = (nx, ny - height * 0.45)
    face[CHIN] = (nx, ny + height * 0.55)
    return face


def hand_at(u: float, v: float, nose=(320.0, 240.0), width=100.0, height=130.0, **kw) -> Hand:
    """A hand whose points all sit at face-frame coordinate (u, v)."""
    p = np.array([nose[0] + u * width, nose[1] + v * height], dtype=np.float32)
    return Hand(center=p, points=np.tile(p, (6, 1)), **kw)


def observation(blendshapes=None, hands=(), with_face=True, pose=None) -> Observation:
    return Observation(
        width=640,
        height=480,
        face=make_face() if with_face else None,
        blendshapes=dict(blendshapes or {}),
        face_matrix=np.eye(4, dtype=np.float32) if with_face else None,
        pose=pose,
        hands=list(hands),
    )
