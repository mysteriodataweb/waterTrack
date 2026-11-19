#!/usr/bin/env bash
# Entraine et evalue le U-Net de detection de l'eau dans un environnement distant
# (Claude Code en ligne, Codespaces, Colab en terminal...). Aucun identifiant n'est necessaire :
# les imagettes sont telechargees depuis la release GitHub publique « unet-data-v1 ».
#
#   cd backend && bash scripts/unet_cloud_train.sh            # 40 epoques (GPU conseille)
#   EPOCHS=12 bash scripts/unet_cloud_train.sh                 # version courte sur CPU
#
# Les resultats (model.pt, history.csv, metrics_test.json) sont copies dans ml/unet_results/,
# dossier suivi par git, pour pouvoir etre commites et recuperes.
set -euo pipefail

cd "$(dirname "$0")/.."
EPOCHS="${EPOCHS:-40}"
BATCH="${BATCH:-32}"
DATA_URL="${DATA_URL:-https://github.com/mysteriodataweb/waterTrack/releases/download/unet-data-v1/watertracker_unet.zip}"
PY="${PYTHON:-python3}"

echo "== Dependances"
if ! "$PY" -c "import torch" 2>/dev/null; then
  "$PY" -m pip install -q torch --index-url https://download.pytorch.org/whl/cpu \
    || "$PY" -m pip install -q torch
fi
"$PY" -m pip install -q -r requirements-unet.txt
"$PY" -c "import torch; print('torch', torch.__version__, '| GPU :', torch.cuda.is_available(), '| threads :', torch.get_num_threads())"

echo "== Imagettes"
if [ ! -f data/unet/manifest.csv ]; then
  mkdir -p data/unet
  curl -fL --retry 5 -C - -o data/unet/watertracker_unet.zip "$DATA_URL"
  # Le zip contient aussi une copie de ml/ : on n'extrait que les donnees
  "$PY" - <<'PYEOF'
import zipfile
with zipfile.ZipFile("data/unet/watertracker_unet.zip") as z:
    z.extractall(".", members=[n for n in z.namelist() if n.startswith("data/unet/")])
PYEOF
  rm -f data/unet/watertracker_unet.zip
fi
echo "$(ls data/unet/chips | wc -l) imagettes"

echo "== Entrainement ($EPOCHS epoques, lots de $BATCH)"
"$PY" -W ignore -m ml.unet_model --data data/unet --out ml/runs/unet_latest --epochs "$EPOCHS" --batch "$BATCH"

echo "== Evaluation sur le jeu de test"
"$PY" -W ignore -m ml.unet_eval --data data/unet --model ml/runs/unet_latest/model.pt --split test

mkdir -p ml/unet_results
cp ml/runs/unet_latest/model.pt ml/runs/unet_latest/history.csv ml/runs/unet_latest/metrics_test.json ml/unet_results/
echo "== Resultats copies dans backend/ml/unet_results/"
