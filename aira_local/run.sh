#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
if [[ ! -x .venv/bin/python ]]; then
 echo 'Run bash aira_local/setup.sh first.' >&2; exit 1
fi
exec .venv/bin/python -m uvicorn aira_local.app:app --host 0.0.0.0 --port "${PORT:-8000}" --no-access-log
