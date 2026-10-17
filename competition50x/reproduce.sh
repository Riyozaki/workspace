#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then python3 -m venv .venv; fi
.venv/bin/python -m pip install --disable-pip-version-check -r competition50x/requirements.txt
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
.venv/bin/python -m competition50x.reproduce "$@"
