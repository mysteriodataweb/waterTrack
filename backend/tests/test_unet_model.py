"""Tests du U-Net de détection de l'eau (ml/unet_model.py) sur des imagettes synthétiques, sans carte graphique."""
import numpy as np
import pytest

torch = pytest.importorskip("torch")

import ml.unet_data as U
import ml.unet_model as M


def synthetic(n: int, size: int = 32, seed: int = 0) -> dict:
    """Imagettes avec un disque d'eau (vert fort, infrarouge faible) sur fond de sol."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[:size, :size]
    x = rng.normal(0.20, 0.02, (n, len(U.BANDS), size, size)).astype(np.float32)
    y = np.zeros((n, size, size), dtype=np.uint8)
    for i in range(n):
        cy, cx, r = rng.integers(8, size - 8, 2).tolist() + [int(rng.integers(4, 8))]
        water = (yy - cy) ** 2 + (xx - cx) ** 2 <= r ** 2
        x[i, U.BANDS.index("B3")][water] = 0.12
        x[i, U.BANDS.index("B8")][water] = 0.04
        x[i, U.BANDS.index("B11")][water] = 0.02
        y[i][water] = U.WATER
    return {"x": x, "y": y, "valid": np.ones((n, size, size), dtype=np.uint8)}


def test_unet_keeps_the_image_size():
    model = M.UNet(base=8, depth=3)
    out = model(torch.zeros(2, M.IN_CHANNELS, 64, 64))
    assert out.shape == (2, 64, 64)


def test_loss_ignores_unlabelled_pixels():
    logits = torch.zeros(1, 4, 4, requires_grad=True)
    target = torch.full((1, 4, 4), U.IGNORE, dtype=torch.uint8)
    assert float(M.masked_loss(logits, target)) == 0
    target[0, 0, 0] = U.WATER
    confident_right = torch.full((1, 4, 4), -9.0)
    confident_right[0, 0, 0] = 9.0
    confident_wrong = -confident_right
    # Seul le pixel étiqueté compte : les 15 autres, pourtant « faux », ne changent rien
    assert float(M.masked_loss(confident_right, target)) < 0.01 < float(M.masked_loss(confident_wrong, target))


def test_pixel_metrics_on_a_known_case():
    labels = np.array([[U.WATER, U.WATER, U.LAND, U.IGNORE]])
    pred = np.array([[True, False, True, True]])
    m = M.pixel_metrics(pred, labels)
    assert (m["precision"], m["recall"]) == (0.5, 0.5)
    assert m["iou"] == pytest.approx(1 / 3) and m["n_pixels"] == 3


def test_radar_agreement_separates_dark_water_from_bright_land():
    pred = np.array([[True, True, False, False]])
    s1 = np.array([[-22.0, -20.0, -9.0, U.NO_S1]], dtype=np.float32)
    out = M.radar_agreement(pred, s1, where=np.ones((1, 4), dtype=bool))
    assert out["dark_in_water"] == 1.0 and out["dark_in_land"] == 0.0 and out["separation"] == 1.0
    assert (out["n_water"], out["n_land"]) == (2, 1)        # le pixel sans radar est écarté


def test_normalisation_uses_training_statistics():
    data = synthetic(4)
    mean, std = M.band_stats(data["x"], data["valid"])
    assert mean.shape == std.shape == (len(U.BANDS),)
    z = M.normalise(data["x"], mean, std)
    assert np.abs(z.mean(axis=(0, 2, 3))).max() < 1e-3


def test_training_learns_to_find_the_water(tmp_path):
    train_set, val_set = synthetic(48, seed=1), synthetic(16, seed=2)
    model, mean, std, history, info = M.train(train_set, val_set, tmp_path, epochs=12, batch=16, base=8, depth=2,
                                              lr=5e-3, device="cpu")
    assert info["best_val_iou"] > 0.85
    assert (tmp_path / "model.pt").exists() and len(history) == 12
    # Le modèle rechargé donne les mêmes probabilités
    again, mean2, std2, info2 = M.load_model(tmp_path / "model.pt")
    p1 = M.predict(model, val_set["x"], mean, std, device="cpu")
    p2 = M.predict(again, val_set["x"], mean2, std2, device="cpu")
    assert np.allclose(p1, p2, atol=1e-5) and info2["best_epoch"] == info["best_epoch"]
    assert M.pixel_metrics(p2 > 0.5, val_set["y"])["iou"] == pytest.approx(info["best_val_iou"], abs=1e-6)
