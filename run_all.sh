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
# ---- 0) generated artifacts are re-created from scratch (committed copies live in git;
#         restore with `git checkout results/` if you want the recorded ones back)
rm -f results/runs.jsonl results/ablations.jsonl results/test_metrics.csv \
      results/timings.csv results/timings_extra.csv results/summary.json \
      results/results.csv results/selected_gaps.json results/exploratory_60ep.jsonl
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

# ---- optional (used in the report, not part of the primary 3-seed pipeline):
# extra quality seeds (CI narrowing)
#   for s in 3 4; do .venv/bin/python experiments/train_all.py --seeds $s --skip-controls; done
# extra latency seeds at batch 1024 (see README) then:
#   .venv/bin/python experiments/analyze.py
# post-hoc exploratory 60-epoch run:
#   .venv/bin/python experiments/exploratory_60ep.py --seeds 0,1,2,3,4
# consistency checks:
#   .venv/bin/python experiments/check_artifacts.py
