# Entraîner le U-Net de détection de l'eau en ligne

Les imagettes (1 768 fichiers, 345 Mo) ne sont pas dans git. Elles sont publiées dans la release GitHub publique
[`unet-data-v1`](https://github.com/mysteriodataweb/waterTrack/releases/tag/unet-data-v1).
Le script `scripts/unet_cloud_train.sh` les télécharge, installe torch, entraîne, évalue sur le jeu de test et copie les résultats dans `ml/unet_results/`.

## Avec Claude Code en ligne (claude.ai/code)

Ouvrir une session sur ce dépôt, branche `main`, puis donner cette consigne :

> Dans `backend/`, lance `EPOCHS=12 bash scripts/unet_cloud_train.sh` (lis d'abord `ml/UNET_TRAINING.md`).
> Si une époque prend plus de 10 minutes, arrête-toi et donne-moi le temps mesuré.
> À la fin, commite `backend/ml/unet_results/` sur une branche `unet-results`, pousse-la, et résume
> `metrics_test.json` : IoU sur les pixels étiquetés, et surtout l'accord avec le radar sur les pixels ambigus
> (U-Net comparé à la règle MNDWI > 0 et à Dynamic World).

L'environnement en ligne n'a pas de GPU : l'entraînement tourne sur le CPU.
Une époque y prend plusieurs minutes, d'où 12 époques au lieu de 40. Avec un GPU (Colab : `notebooks/WaterTracker_unet_colab.ipynb`), garder 40.

## Récupérer les résultats en local

```bash
git fetch origin unet-results
git checkout origin/unet-results -- backend/ml/unet_results
```

`model.pt` se recharge avec `ml.unet_model.load_model`. L'inventaire automatique (`python -m ml.unet_inventory`) se lance ensuite en local, car il a besoin d'Earth Engine.
