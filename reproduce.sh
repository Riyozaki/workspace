#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install --quiet -r requirements.txt
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 NUMEXPR_NUM_THREADS=2
export VECLIB_MAXIMUM_THREADS=2 BLIS_NUM_THREADS=2 PYTHONHASHSEED=0
exec .venv/bin/python -m tensor_gp.reproduce "$@"
