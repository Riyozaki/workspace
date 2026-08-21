#!/usr/bin/env bash
# Reproducible 3D runtime bootstrap for the restricted Arena environment.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SKIP_BLENDER=0
if [[ "${1:-}" == "--skip-blender" ]]; then
  SKIP_BLENDER=1
fi

if [[ ! -x .venv/bin/python ]] || [[ ! -d node_modules ]]; then
  scripts/bootstrap-documents.sh --skip-system
else
  # requirements.lock may have gained modeling dependencies since the last bootstrap.
  PIP_NO_CACHE_DIR=1 .venv/bin/python -m pip install --require-hashes -r requirements.lock
  .venv/bin/python -m pip install --no-deps -e .
  npm ci --ignore-scripts --no-audit --no-fund
fi

RUNTIME="$ROOT/.cache/model-runtime"
LIBS="$RUNTIME/headless-libs"
mkdir -p "$RUNTIME"
tools/headless-3d-shims/build.sh "$LIBS"

if [[ "$SKIP_BLENDER" -eq 0 ]]; then
  BLENDER="$RUNTIME/blender"
  if [[ ! -x "$BLENDER/bin/python" ]]; then
    python3 -m venv "$BLENDER"
  fi
  PIP_NO_CACHE_DIR=1 "$BLENDER/bin/python" -m pip install --upgrade pip
  PIP_NO_CACHE_DIR=1 "$BLENDER/bin/python" -m pip install --require-hashes -r requirements-blender.lock
  VERSION="$(LD_LIBRARY_PATH="$LIBS${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" "$BLENDER/bin/python" - <<'PY'
import bpy
print(bpy.app.version_string)
PY
)"
  "$ROOT/.venv/bin/python" - "$RUNTIME/blender-runtime.json" "$BLENDER/bin/python" "$VERSION" <<'PY'
import json, pathlib, sys
path, python, version = sys.argv[1:]
pathlib.Path(path).write_text(json.dumps({
    "available": True,
    "provider": "official Blender Foundation bpy wheel",
    "python": str(pathlib.Path(python).absolute()),
    "version": version,
    "renderer": "Cycles CPU",
    "headless_compatibility_shims": True,
}, indent=2) + "\n")
PY
fi

scripts/modelctl doctor --self-test
cat <<'EOF'

Modeling bootstrap finished.

Use:
  scripts/modelctl --help
  scripts/modelctl create examples/modeling/lounge-chair.json .model-work/lounge-chair.glb --render

The local Blender runtime is headless-only: Cycles CPU, declarative workers, no GUI/EEVEE.
EOF
