#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p artifacts
if [[ ! -x .venv/bin/python ]]; then python3 -m venv .venv; fi
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export CMAKE_BUILD_PARALLEL_LEVEL=2
if [[ "$(uname -m)" == 'x86_64' ]]; then
 export CMAKE_ARGS='-DGGML_CUDA=OFF -DGGML_NATIVE=OFF -DGGML_AVX2=ON -DGGML_AVX512=OFF -DGGML_AVX512_VNNI=OFF -DLLAMA_CURL=OFF'
else
 export CMAKE_ARGS='-DGGML_CUDA=OFF -DGGML_NATIVE=OFF -DLLAMA_CURL=OFF'
fi
.venv/bin/python -m pip install --disable-pip-version-check -r aira_local/requirements.txt
.venv/bin/python -m aira_local.setup_model
if [[ ! -f aira_local/models/budget_router.json ]]; then
 .venv/bin/python -m aira_local.build_data
 .venv/bin/python -m aira_local.train_router
fi
.venv/bin/python -m aira_local.build_seed
printf '\nReady. Start with: bash aira_local/run.sh\n'
