#!/usr/bin/env bash
# setup.sh — build the document toolchain from scratch.
#
# Safe to re-run: it is incremental and idempotent.
# Everything installs into the repo (.venv/ and tools/node_modules/), both of
# which are gitignored. No sudo, no apt — this sandbox has neither a working
# Debian mirror nor access to dotnet/LibreOffice downloads.
#
#   bash tools/setup.sh            # install
#   bash tools/setup.sh --check    # verify only, install nothing

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$REPO_ROOT/.venv"
PY="$VENV/bin/python"
CHECK_ONLY=0
[[ "${1:-}" == "--check" ]] && CHECK_ONLY=1

say()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
die()  { printf '  \033[31m✗\033[0m %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- prerequisites
command -v python3 >/dev/null || die "python3 not found"
command -v node    >/dev/null || die "node not found"
command -v npm     >/dev/null || die "npm not found"
ok "python3 $(python3 --version 2>&1 | cut -d' ' -f2), node $(node --version)"

if [[ $CHECK_ONLY -eq 0 ]]; then
  # ------------------------------------------------------------------- python
  say "Python environment"
  [[ -d "$VENV" ]] || python3 -m venv "$VENV"
  "$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet -r "$REPO_ROOT/tools/requirements.txt"
  ok "installed $(grep -cE '^[a-zA-Z]' "$REPO_ROOT/tools/requirements.txt") python packages"

  # --------------------------------------------------------------------- node
  say "Node environment"
  (cd "$REPO_ROOT" && npm install --silent --no-audit --no-fund)
  ok "installed node packages"

  # ------------------------------------------------------- chromium native deps
  say "Chromium native dependencies"
  (cd "$REPO_ROOT" && node -e "require('./tools/js/chromium.js').ensureNativeDeps()")
  ok "inflated libnspr4/libnss3 + bundled fonts"

  # -------------------------------------------------------------------- fonts
  say "Fonts"
  "$PY" "$REPO_ROOT/tools/install_fonts.py" || die "font installation failed"
fi

# ------------------------------------------------------------------- verify
say "Verifying toolchain"
[[ -x "$PY" ]] || die "venv missing — run without --check first"

"$PY" - <<'PYCHECK'
import importlib, sys
mods = ["openpyxl","docx","pptx","formulas","pypdf","pypdfium2","pdfplumber",
        "reportlab","pypandoc","typst","lxml","defusedxml","matplotlib","PIL",
        "fontTools","brotli"]
bad = []
for m in mods:
    try: importlib.import_module(m)
    except Exception as e: bad.append(f"{m}: {e}")
if bad:
    print("  \033[31m✗\033[0m python imports failed:"); [print("    ", b) for b in bad]; sys.exit(1)
print(f"  \033[32m✓\033[0m {len(mods)} python modules import cleanly")

import pypandoc
print(f"  \033[32m✓\033[0m pandoc {pypandoc.get_pandoc_version()} (bundled)")
PYCHECK

(cd "$REPO_ROOT" && node -e "
const need = ['docx','pptxgenjs','exceljs','puppeteer-core','@sparticuz/chromium'];
const bad = need.filter(m => { try { require.resolve(m); return false } catch { return true } });
if (bad.length) { console.error('  \x1b[31m✗\x1b[0m missing node modules: ' + bad.join(', ')); process.exit(1) }
console.log('  \x1b[32m✓\x1b[0m ' + need.length + ' node modules resolve');
")

say "Smoke test: render a PDF through headless Chromium"
(cd "$REPO_ROOT" && node -e "
const {launch} = require('./tools/js/chromium.js');
(async () => {
  const b = await launch();
  const p = await b.newPage();
  await p.setContent('<h1 style=\"font-family:sans-serif\">Проверка · Check · 検査</h1>');
  await p.pdf({ path: require('os').tmpdir() + '/toolchain-smoke.pdf', format: 'A4' });
  await b.close();
  console.log('  \x1b[32m✓\x1b[0m chromium renders PDF (cyrillic ok)');
})().catch(e => { console.error('  \x1b[31m✗\x1b[0m ' + e.message.split('\n')[0]); process.exit(1) });
")

printf '\n\033[1;32mToolchain ready.\033[0m Activate with:  source .venv/bin/activate\n'
