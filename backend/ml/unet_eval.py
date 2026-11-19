"""
Évaluation du U-Net de détection de l'eau sur le jeu de test (blocs jamais vus).

Trois lectures, de la moins à la plus informative :

  1. Pixels étiquetés (cas nets). Les étiquettes exigent MNDWI > 0,10 pour « eau »
     et < −0,10 pour « pas eau » : la règle opérationnelle (MNDWI > 0) y obtient
     donc 100 % PAR CONSTRUCTION. Cette lecture vérifie seulement que le réseau
     reproduit les cas nets ; elle ne peut pas montrer qu'il fait mieux.

  2. Pixels ambigus (ignorés à l'entraînement). Aucune étiquette n'existe : on
     juge chaque carte avec le radar Sentinel-1, que le réseau n'a jamais vu.
     L'eau libre est sombre au radar ; une bonne carte met beaucoup de pixels
     sombres dans « eau » et peu dans « pas eau ».

  3. Désaccords entre le réseau et la règle opérationnelle : qui le radar
     soutient-il ?

Limite : le radar n'est pas une vérité de terrain (vent, végétation émergée,
sols lisses et secs sombres aussi). Il départage, il ne certifie pas.

Usage :
  python -m ml.unet_eval --data data/unet --model ml/runs/unet_latest/model.pt
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import unet_data as U
from . import unet_model as M


def evaluate(data: dict, prob: np.ndarray) -> dict:
    """Compare le réseau, la règle MNDWI > 0 et Dynamic World sur un jeu d'imagettes."""
    maps = {
        "unet": prob > 0.5,
        "mndwi_threshold": np.stack([U.threshold_baseline(x) for x in data["x"]]),
        "dynamic_world": data["dw_water"] >= U.DW_WATER,
    }
    valid = data["valid"] > 0
    ambiguous = valid & (data["y"] == U.IGNORE)
    out = {
        "n_chips": int(len(data["x"])),
        "ambiguous_share_of_valid": float(ambiguous.sum() / max(valid.sum(), 1)),
        "labelled": {name: M.pixel_metrics(pred, data["y"]) for name, pred in maps.items()},
        "radar_ambiguous": {name: M.radar_agreement(pred, data["s1_vv"], ambiguous) for name, pred in maps.items()},
        "radar_all_valid": {name: M.radar_agreement(pred, data["s1_vv"], valid) for name, pred in maps.items()},
    }
    # Désaccords réseau / règle opérationnelle : part de pixels sombres au radar de chaque côté
    has_s1 = valid & (data["s1_vv"] > U.NO_S1)
    dark = data["s1_vv"] < M.S1_DARK_DB
    only_unet = has_s1 & maps["unet"] & ~maps["mndwi_threshold"]
    only_rule = has_s1 & ~maps["unet"] & maps["mndwi_threshold"]
    out["disagreement"] = {
        "unet_water_rule_land": {"n": int(only_unet.sum()), "radar_dark": float(dark[only_unet].mean()) if only_unet.any() else None},
        "rule_water_unet_land": {"n": int(only_rule.sum()), "radar_dark": float(dark[only_rule].mean()) if only_rule.any() else None},
        "radar_dark_agreed_water": float(dark[has_s1 & maps["unet"] & maps["mndwi_threshold"]].mean()),
        "radar_dark_agreed_land": float(dark[has_s1 & ~maps["unet"] & ~maps["mndwi_threshold"]].mean()),
    }
    # Surface en eau totale selon chaque carte (hectares, pixels de 10 m)
    out["water_area_ha"] = {name: float((pred & valid).sum() * U.SCALE_M ** 2 / 1e4) for name, pred in maps.items()}
    return out


def main() -> None:
    backend = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Évalue le U-Net de détection de l'eau")
    parser.add_argument("--data", type=Path, default=backend / "data" / "unet")
    parser.add_argument("--model", type=Path, default=backend / "ml" / "runs" / "unet_latest" / "model.pt")
    parser.add_argument("--split", default="test")
    args = parser.parse_args()

    manifest = M.usable(pd.read_csv(args.data / "manifest.csv"))
    data = M.load_chips(manifest[manifest["split"] == args.split], args.data / "chips")
    model, mean, std, info = M.load_model(args.model)
    result = evaluate(data, M.predict(model, data["x"], mean, std))
    result["split"], result["training"] = args.split, info
    (args.model.parent / f"metrics_{args.split}.json").write_text(json.dumps(result, indent=2, default=float), encoding="utf-8")

    print(f"{result['n_chips']} imagettes ({args.split}) ; pixels ambigus : {result['ambiguous_share_of_valid']:.1%} des pixels valides")
    for key in ("labelled", "radar_ambiguous", "radar_all_valid"):
        print(f"\n{key}")
        print(pd.DataFrame(result[key]).T.round(4).to_string())
    print("\ndisagreement")
    print(json.dumps(result["disagreement"], indent=2))
    print("\nsurface en eau (ha) :", {k: round(v) for k, v in result["water_area_ha"].items()})


if __name__ == "__main__":
    main()
