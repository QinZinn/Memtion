import cv2
import numpy as np

from memtion.render import BG, MemePanel


def _white_image(tmp_path):
    path = tmp_path / "white.png"
    cv2.imwrite(str(path), np.full((100, 100, 3), 255, np.uint8))
    return path


def test_no_caption_by_default_image_fills_panel(tmp_path):
    panel = MemePanel(200).render("m", _white_image(tmp_path), "Hahaha!")
    assert panel.shape == (200, 200, 3)
    assert (panel[-1] == 255).all()  # the image reaches the bottom edge, no caption band


def test_caption_band_when_enabled(tmp_path):
    panel = MemePanel(200, show_label=True).render("m", _white_image(tmp_path), "Hahaha!")
    band = panel[-MemePanel.LABEL_H :]
    assert (band == BG).mean() > 0.5  # dark band...
    assert (band > 200).any()  # ...with light caption text on it


def test_toggling_caption_does_not_reuse_stale_cache(tmp_path):
    panel = MemePanel(200)
    image = _white_image(tmp_path)
    without = panel.render("m", image, "Hahaha!").copy()
    panel.show_label = True
    assert not np.array_equal(without, panel.render("m", image, "Hahaha!"))
