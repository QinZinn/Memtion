"""Entry point for the PyInstaller build."""

import os
import sys

# mediapipe imports matplotlib.pyplot at import time; keep it off any GUI toolkit.
os.environ.setdefault("MPLBACKEND", "Agg")

from memtion.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
