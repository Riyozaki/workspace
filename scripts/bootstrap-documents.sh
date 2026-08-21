#!/usr/bin/env bash
# Reproducible local bootstrap for the document toolchain.
# System packages are installed only when missing. Python dependencies live in .venv.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SKIP_SYSTEM=0
if [[ "${1:-}" == "--skip-system" ]]; then
  SKIP_SYSTEM=1
fi

need_system=0
for command in soffice pandoc; do
  command -v "$command" >/dev/null 2>&1 || need_system=1
done

if [[ "$SKIP_SYSTEM" -eq 0 && "$need_system" -eq 1 ]]; then
  if command -v apt-get >/dev/null 2>&1; then
    SUDO=()
    if [[ "$(id -u)" -ne 0 ]]; then
      command -v sudo >/dev/null 2>&1 || {
        echo "System packages are missing and sudo is unavailable." >&2
        echo "Re-run with --skip-system and set DOCUMENT_SYSTEM_SOFFICE manually." >&2
        exit 1
      }
      SUDO=(sudo)
    fi
    echo "Installing LibreOffice, Pandoc, Poppler, fonts, and Python venv support..."
    if ! "${SUDO[@]}" apt-get update; then
      echo "apt-get update failed (often because this sandbox blocks Debian mirrors)." >&2
      echo "Continuing with Python setup; rendering will remain unavailable until soffice is provided." >&2
    elif ! DEBIAN_FRONTEND=noninteractive "${SUDO[@]}" apt-get install -y --no-install-recommends \
      libreoffice-writer libreoffice-calc libreoffice-impress \
      pandoc poppler-utils qpdf tesseract-ocr tesseract-ocr-eng fontconfig \
      fonts-dejavu-core fonts-liberation2 fonts-noto-core fonts-noto-cjk \
      fonts-crosextra-carlito fonts-crosextra-caladea python3-venv; then
      echo "System package installation failed; continuing with Python-only setup." >&2
    fi
  else
    echo "No supported system package manager found; skipping system dependencies." >&2
  fi
fi

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip setuptools wheel
if [[ -f requirements.lock ]]; then
  .venv/bin/python -m pip install --require-hashes -r requirements.lock
  .venv/bin/python -m pip install --no-deps -e .
else
  .venv/bin/python -m pip install -e '.[dev]'
fi

if command -v npm >/dev/null 2>&1 && [[ -f package-lock.json ]]; then
  echo "Installing pinned JavaScript/WASM runtimes..."
  npm ci --ignore-scripts --no-audit --no-fund
fi

echo
.venv/bin/documentctl env || true
echo
cat <<'EOF'
Bootstrap finished.

If soffice is still null, install LibreOffice in the runtime or set:
  export DOCUMENT_SYSTEM_SOFFICE=/absolute/path/to/soffice

Use:
  scripts/documentctl --help
  .venv/bin/pytest
EOF
