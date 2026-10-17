#!/usr/bin/env bash
# Full reproduction. Requires python3-venv, curl, tar. ~XX min on 2 vCPU.
set -euo pipefail
cd "$(dirname "$0")"
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-2}
export OPENBLAS_NUM_THREADS=${OPENBLAS_NUM_THREADS:-2}
export MKL_NUM_THREADS=${MKL_NUM_THREADS:-2}

if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet numpy scipy
fi

# ---- data (official Fashion-MNIST repo; skipped if already downloaded)
mkdir -p data/fashion
if [ ! -f data/fashion/train-images-idx3-ubyte.gz ]; then
  TMP=$(mktemp -d)
  curl -sL https://codeload.github.com/zalandoresearch/fashion-mnist/tar.gz/refs/heads/master -o "$TMP/fm.tar.gz"
  tar -xzf "$TMP/fm.tar.gz" -C "$TMP" fashion-mnist-master/data/fashion
  cp "$TMP"/fashion-mnist-master/data/fashion/*.gz data/fashion/
  rm -rf "$TMP"
fi

mkdir -p results
# ---- 1) baseline configuration grid (validation only). Skipped if frozen config exists.
if [ ! -f results/frozen_config.json ]; then
  .venv/bin/python experiments/phase1_baseline_grid.py | tee results/phase1.log
  .venv/bin/python - <<'PY'
import json
from pathlib import Path
g = json.loads(Path("results/phase1_grid.json").read_text())
best = g["best"]
cfg = {"lr": best["lr"], "dropout": best["dropout"], "student_lr": 1e-3,
       "source": "results/phase1_grid.json (validation only)"}
Path("results/frozen_config.json").write_text(json.dumps(cfg, indent=2))
print("frozen config:", cfg)
PY
fi

# ---- 2) main training sweep (no test access)
.venv/bin/python experiments/train_all.py --seeds 0,1,2 --time-budget 2400

# ---- 3) freeze selection using validation only
.venv/bin/python experiments/select.py

# ---- 4) ablations at the frozen width (validation only)
.venv/bin/python experiments/ablations.py

# ---- 5) the single test-set evaluation
.venv/bin/python experiments/evaluate_test.py

# ---- 6) latency benchmark + aggregation
.venv/bin/python experiments/bench.py
.venv/bin/python experiments/analyze.py
