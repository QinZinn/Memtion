# PyInstaller spec: `pyinstaller packaging/memtion.spec` from the repository root.
# Download the models first: `python -m memtion --download-models`.
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).resolve().parent
MODELS = ROOT / "models"
if not any(MODELS.glob("*.task")):
    raise SystemExit("models/ is empty - run `python -m memtion --download-models` first")

datas = [(str(ROOT / d), d) for d in ("packs", "Sample_Meme", "Blob_Meme", "models")]
mp_datas, mp_binaries, mp_hidden = collect_all("mediapipe")

a = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT)],
    binaries=mp_binaries,
    datas=datas + mp_datas,
    hiddenimports=mp_hidden,
    excludes=["tkinter", "sounddevice", "pytest", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)

is_mac = sys.platform == "darwin"
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="memtion",
    console=not is_mac,  # the macOS .app is launched from Finder; elsewhere keep the log window
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="memtion", upx=False)

if is_mac:
    app = BUNDLE(
        coll,
        name="Memtion.app",
        bundle_identifier="io.github.qinzinn.memtion",
        info_plist={
            "CFBundleShortVersionString": "0.1.0",
            "NSCameraUsageDescription": "Memtion dùng camera để nhận diện biểu cảm và tư thế của bạn.",
            "NSHighResolutionCapable": True,
        },
    )
