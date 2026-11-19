"""
U-Net de détection de l'eau pixel par pixel sur Sentinel-2 (10 m).

Entrée : 6 bandes Sentinel-2 d'une imagette (voir `ml/unet_data.py`).
Sortie : probabilité « eau » de chaque pixel.

Le réseau est entraîné sur les étiquettes de consensus : les pixels ambigus ou
nuageux ne comptent pas dans la fonction de coût. Il apprend sur les cas nets,
avec le voisinage et toutes les bandes, puis est jugé sur les cas ambigus avec
une source qu'il n'a jamais vue (radar Sentinel-1).

Usage :
  python -m ml.unet_model --data data/unet --out ml/runs/unet_latest
"""
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from torch import nn

from . import unet_data as U

logger = logging.getLogger("unet_model")

IN_CHANNELS = len(U.BANDS)
REFLECTANCE_MAX = 1.0             # réflectances bornées avant normalisation (reflets, nuages résiduels)
S1_DARK_DB = -18.0                # rétrodiffusion VV sous laquelle une surface est « lisse comme de l'eau »


# --------------------------------------------------------------------------- #
# Réseau
# --------------------------------------------------------------------------- #
class DoubleConv(nn.Sequential):
    def __init__(self, n_in: int, n_out: int):
        super().__init__(
            nn.Conv2d(n_in, n_out, 3, padding=1, bias=False), nn.BatchNorm2d(n_out), nn.ReLU(inplace=True),
            nn.Conv2d(n_out, n_out, 3, padding=1, bias=False), nn.BatchNorm2d(n_out), nn.ReLU(inplace=True),
        )


class UNet(nn.Module):
    """U-Net classique : `depth` descentes, autant de remontées avec liaisons directes."""

    def __init__(self, in_channels: int = IN_CHANNELS, base: int = 24, depth: int = 3):
        super().__init__()
        widths = [base * 2 ** i for i in range(depth + 1)]
        self.down = nn.ModuleList([DoubleConv(in_channels, widths[0])] +
                                  [DoubleConv(widths[i], widths[i + 1]) for i in range(depth)])
        self.up = nn.ModuleList([nn.ConvTranspose2d(widths[i + 1], widths[i], 2, stride=2) for i in reversed(range(depth))])
        self.merge = nn.ModuleList([DoubleConv(2 * widths[i], widths[i]) for i in reversed(range(depth))])
        self.head = nn.Conv2d(widths[0], 1, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        skips = []
        for i, block in enumerate(self.down):
            x = block(x if i == 0 else F.max_pool2d(x, 2))
            skips.append(x)
        skips.pop()
        for up, merge in zip(self.up, self.merge):
            x = merge(torch.cat([up(x), skips.pop()], dim=1))
        return self.head(x).squeeze(1)


# --------------------------------------------------------------------------- #
# Données
# --------------------------------------------------------------------------- #
def load_chips(manifest: pd.DataFrame, chips_dir: Path) -> dict[str, np.ndarray]:
    """Charge les imagettes du manifeste en mémoire : entrées, étiquettes et sources annexes."""
    x, y, dw, s1, valid = [], [], [], [], []
    for chip_id in manifest["chip_id"]:
        chip = np.load(chips_dir / f"{chip_id}.npz")
        # Demi-précision en mémoire (moitié moins de place) ; calculs en float32 au besoin
        x.append(chip["x"].astype(np.float16))
        y.append(U.make_labels(chip["x"].astype(np.float32), chip["dw_water"].astype(np.float32), chip["valid"]))
        dw.append(chip["dw_water"].astype(np.float16))
        s1.append(chip["s1_vv"].astype(np.float16))
        valid.append(chip["valid"])
    return {"x": np.stack(x), "y": np.stack(y), "dw_water": np.stack(dw), "s1_vv": np.stack(s1), "valid": np.stack(valid)}


def band_stats(x: np.ndarray, valid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Moyenne et écart-type par bande sur les pixels valides (jeu d'entraînement seulement)."""
    keep = valid > 0
    mean, std = [], []
    for b in range(x.shape[1]):                      # bande par bande : pas de copie du jeu entier
        pixels = np.clip(x[:, b][keep].astype(np.float64), 0, REFLECTANCE_MAX)
        mean.append(pixels.mean())
        std.append(pixels.std() + 1e-6)
    return np.array(mean, dtype=np.float32), np.array(std, dtype=np.float32)


def normalise(x: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    """Imagettes [N, bandes, H, W] en réflectance -> centrées-réduites par bande."""
    x = np.clip(np.asarray(x, dtype=np.float32), 0, REFLECTANCE_MAX)
    return ((x - mean[None, :, None, None]) / std[None, :, None, None]).astype(np.float32)


class ChipDataset(torch.utils.data.Dataset):
    """Imagettes en réflectance, normalisées à la lecture ; `augment` : symétries et quarts de tour aléatoires."""

    def __init__(self, x: np.ndarray, y: np.ndarray, mean: np.ndarray, std: np.ndarray,
                 augment: bool = False, seed: int = 0):
        self.x, self.y, self.mean, self.std, self.augment = x, y, mean, std, augment
        self.rng = np.random.default_rng(seed)

    def __len__(self) -> int:
        return len(self.x)

    def __getitem__(self, i: int):
        x, y = normalise(self.x[i][None], self.mean, self.std)[0], self.y[i]
        if self.augment:
            k = int(self.rng.integers(4))
            x, y = np.rot90(x, k, axes=(1, 2)), np.rot90(y, k)
            if self.rng.random() < 0.5:
                x, y = x[:, :, ::-1], y[:, ::-1]
        return torch.from_numpy(np.ascontiguousarray(x)), torch.from_numpy(np.ascontiguousarray(y))


# --------------------------------------------------------------------------- #
# Fonction de coût et mesures
# --------------------------------------------------------------------------- #
def masked_loss(logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """Entropie croisée + Dice, calculées sur les seuls pixels étiquetés (les 255 sont ignorés)."""
    keep = target != U.IGNORE
    if not keep.any():
        return logits.sum() * 0
    z, t = logits[keep], target[keep].float()
    bce = F.binary_cross_entropy_with_logits(z, t)
    p = torch.sigmoid(z)
    dice = 1 - (2 * (p * t).sum() + 1) / (p.sum() + t.sum() + 1)
    return bce + dice


def pixel_metrics(pred: np.ndarray, labels: np.ndarray) -> dict:
    """Précision, rappel, F1 et IoU de la classe « eau » sur les pixels étiquetés."""
    keep = labels != U.IGNORE
    p, t = pred[keep].astype(bool), labels[keep] == U.WATER
    tp, fp, fn = int((p & t).sum()), int((p & ~t).sum()), int((~p & t).sum())
    precision = tp / (tp + fp) if tp + fp else float("nan")
    recall = tp / (tp + fn) if tp + fn else float("nan")
    return {"precision": precision, "recall": recall,
            "f1": 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else float("nan"),
            "iou": tp / (tp + fp + fn) if tp + fp + fn else float("nan"),
            "n_water": int(t.sum()), "n_pixels": int(keep.sum())}


def radar_agreement(pred: np.ndarray, s1_vv: np.ndarray, where: np.ndarray) -> dict:
    """Accord avec le radar sur les pixels `where` (par exemple les pixels ambigus).

    L'eau libre renvoie peu d'écho radar (surface lisse) : parmi les pixels
    déclarés « eau », une forte part doit être sombre en VV ; parmi les « pas eau »,
    une faible part. L'écart entre les deux mesure ce que la carte sépare vraiment.
    """
    ok = where & (s1_vv > U.NO_S1)
    dark = s1_vv < S1_DARK_DB
    water, land = ok & pred.astype(bool), ok & ~pred.astype(bool)
    dark_in_water = float(dark[water].mean()) if water.any() else float("nan")
    dark_in_land = float(dark[land].mean()) if land.any() else float("nan")
    return {"dark_in_water": dark_in_water, "dark_in_land": dark_in_land,
            "separation": dark_in_water - dark_in_land, "n_water": int(water.sum()), "n_land": int(land.sum())}


# --------------------------------------------------------------------------- #
# Prédiction
# --------------------------------------------------------------------------- #
@torch.no_grad()
def predict(model: UNet, x: np.ndarray, mean: np.ndarray, std: np.ndarray, batch: int = 64,
            device: str | None = None) -> np.ndarray:
    """Probabilité « eau » par pixel pour des imagettes [N, 6, H, W] en réflectance 0-1."""
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device).eval()
    out = []
    for start in range(0, len(x), batch):
        xb = torch.from_numpy(normalise(x[start:start + batch], mean, std))
        out.append(torch.sigmoid(model(xb.to(device))).float().cpu().numpy())
    return np.concatenate(out) if out else np.zeros((0, *x.shape[2:]), dtype=np.float32)


def save_model(path: Path, model: UNet, mean: np.ndarray, std: np.ndarray, config: dict, info: dict) -> None:
    torch.save({"state": model.state_dict(), "mean": mean, "std": std, "config": config, "info": info}, path)


def load_model(path: Path) -> tuple[UNet, np.ndarray, np.ndarray, dict]:
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    model = UNet(**ckpt["config"])
    model.load_state_dict(ckpt["state"])
    return model.eval(), ckpt["mean"], ckpt["std"], ckpt["info"]


# --------------------------------------------------------------------------- #
# Entraînement
# --------------------------------------------------------------------------- #
def train(train_set: dict, val_set: dict, out_dir: Path | None = None, epochs: int = 40, batch: int = 32,
          lr: float = 2e-3, base: int = 24, depth: int = 3, seed: int = 42, device: str | None = None):
    """Entraîne le U-Net ; garde les poids de la meilleure époque en validation (IoU de l'eau)."""
    torch.manual_seed(seed)
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    mean, std = band_stats(train_set["x"], train_set["valid"])
    config = {"in_channels": train_set["x"].shape[1], "base": base, "depth": depth}
    model = UNet(**config).to(device)

    n_train = len(train_set["x"])
    loader = torch.utils.data.DataLoader(ChipDataset(train_set["x"], train_set["y"], mean, std, augment=True, seed=seed),
                                         batch_size=batch, shuffle=True, drop_last=n_train > batch)
    optimiser = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    schedule = torch.optim.lr_scheduler.OneCycleLR(optimiser, max_lr=lr, total_steps=epochs * len(loader))
    scaler = torch.amp.GradScaler(enabled=device == "cuda")

    history, best_iou, best_state = [], -1.0, None
    for epoch in range(1, epochs + 1):
        model.train()
        total, t0 = 0.0, time.time()
        for xb, yb in loader:
            xb, yb = xb.to(device), yb.to(device)
            optimiser.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device, enabled=device == "cuda"):
                loss = masked_loss(model(xb).float(), yb)
            scaler.scale(loss).backward()
            scaler.step(optimiser)
            scaler.update()
            schedule.step()
            total += float(loss) * len(xb)
        prob = predict(model, val_set["x"], mean, std, device=device)
        val = pixel_metrics(prob > 0.5, val_set["y"])
        history.append({"epoch": epoch, "train_loss": total / len(loader.dataset), "val_iou": val["iou"],
                        "val_precision": val["precision"], "val_recall": val["recall"], "seconds": time.time() - t0})
        logger.info("époque %2d | coût %.4f | validation IoU %.4f (précision %.3f, rappel %.3f) | %.0f s",
                    epoch, history[-1]["train_loss"], val["iou"], val["precision"], val["recall"], history[-1]["seconds"])
        if val["iou"] > best_iou:
            best_iou = val["iou"]
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    history = pd.DataFrame(history)
    info = {"best_val_iou": best_iou, "best_epoch": int(history["val_iou"].idxmax()) + 1, "epochs": epochs,
            "n_train": len(train_set["x"]), "n_val": len(val_set["x"]), "bands": U.BANDS, "seed": seed}
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        save_model(out_dir / "model.pt", model, mean, std, config, info)
        history.to_csv(out_dir / "history.csv", index=False)
    return model.cpu().eval(), mean, std, history, info


def usable(manifest: pd.DataFrame) -> pd.DataFrame:
    """Imagettes qui portent au moins un pixel étiqueté (Dynamic World présent, pas tout nuageux)."""
    return manifest[manifest["ignore_frac"] < 1.0].reset_index(drop=True)


def main() -> None:
    backend = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Entraîne le U-Net de détection de l'eau")
    parser.add_argument("--data", type=Path, default=backend / "data" / "unet")
    parser.add_argument("--out", type=Path, default=backend / "ml" / "runs" / "unet_latest")
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch", type=int, default=32)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    manifest = usable(pd.read_csv(args.data / "manifest.csv"))
    sets = {s: load_chips(manifest[manifest["split"] == s], args.data / "chips") for s in ("train", "val")}
    logger.info("entraînement : %d imagettes | validation : %d | appareil : %s", len(sets["train"]["x"]),
                len(sets["val"]["x"]), "cuda" if torch.cuda.is_available() else "cpu")
    *_, info = train(sets["train"], sets["val"], args.out, epochs=args.epochs, batch=args.batch)
    logger.info("meilleure époque %d : IoU de validation %.4f -> %s", info["best_epoch"], info["best_val_iou"], args.out)


if __name__ == "__main__":
    main()
