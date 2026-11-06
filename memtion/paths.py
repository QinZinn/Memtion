"""Where bundled resources and user files live, from source or a frozen build."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def resource_root() -> Path:
    """Folder holding packs/, models/ and the meme images.

    In a PyInstaller build everything is unpacked under `sys._MEIPASS`;
    from a source checkout it is the repository root.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def user_dir() -> Path:
    """Per-user, writable config folder (extra packs go in `<user_dir>/packs`)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home())
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "memtion"


def screenshot_dir() -> Path:
    pictures = Path.home() / "Pictures"
    return (pictures if pictures.is_dir() else Path.home()) / "Memtion"


RESOURCE_ROOT = resource_root()
BUNDLED_PACKS = RESOURCE_ROOT / "packs"
USER_PACKS = user_dir() / "packs"
