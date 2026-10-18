#!/bin/bash
# Browser checks need Chromium. In this sandbox it comes from the npm package @sparticuz/chromium
# (installed under $TOOLS, default /home/user/tools) plus its bundled Amazon Linux libs.
# Usage: PORT=3000 ./tools/run-browser-checks.sh  (start the server first: npm start)
TOOLS=${TOOLS:-/home/user/tools}
export LD_LIBRARY_PATH=$TOOLS/chromelibs/lib:$TOOLS/chromelibs/lib64:$LD_LIBRARY_PATH
cd "$TOOLS" && node "$OLDPWD/tools/e2e.mjs" "$OLDPWD/screenshots" "http://127.0.0.1:${PORT:-3000}"
