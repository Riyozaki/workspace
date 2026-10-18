#!/bin/bash
# Headless Chromium checks: loads the game, plays through the UI API, clicks a relic, takes screenshots,
# and reports console errors. Chromium comes from the npm package @sparticuz/chromium (installed into tools/).
# Usage: (in another terminal) npm start   then   ./tools/run-browser-checks.sh [baseUrl]
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
BASE="${1:-http://127.0.0.1:${PORT:-3000}}"
cd "$HERE"
[ -d node_modules ] || npm install --no-audit --no-fund
# @sparticuz/chromium ships its runtime libs as a brotli-compressed tarball; unpack once.
if [ ! -d chromelibs/lib ]; then
  node -e "const z=require('zlib'),f=require('fs');f.mkdirSync('chromelibs',{recursive:true});f.writeFileSync('chromelibs/al2023.tar',z.brotliDecompressSync(f.readFileSync('node_modules/@sparticuz/chromium/bin/al2023.tar.br')))"
  tar -xf chromelibs/al2023.tar -C chromelibs
fi
export LD_LIBRARY_PATH="$HERE/chromelibs/lib:$HERE/chromelibs/lib64:$LD_LIBRARY_PATH"
node "$HERE/e2e.mjs" "$ROOT/screenshots" "$BASE"
