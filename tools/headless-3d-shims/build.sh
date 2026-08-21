#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
OUT="${1:?Usage: build.sh OUTPUT_DIR}"
mkdir -p "$OUT"
CC="${CC:-gcc}"
command -v "$CC" >/dev/null 2>&1 || { echo "A C compiler is required for headless compatibility shims" >&2; exit 1; }

for soname in libXrender.so.1 libSM.so.6 libICE.so.6; do
  "$CC" -shared -fPIC "$ROOT/empty-stub.c" -Wl,-soname,"$soname" -o "$OUT/$soname"
done
"$CC" -shared -fPIC "$ROOT/xfixes-stub.c" -Wl,-soname,libXfixes.so.3 -o "$OUT/libXfixes.so.3"
"$CC" -shared -fPIC "$ROOT/xi-stub.c" -Wl,-soname,libXi.so.6 -o "$OUT/libXi.so.6"
"$CC" -shared -fPIC "$ROOT/xkb-stub.c" -Wl,-soname,libxkbcommon.so.0 \
  -Wl,--version-script="$ROOT/xkb.map" -o "$OUT/libxkbcommon.so.0"
"$CC" -shared -fPIC "$ROOT/gl-stub.c" -Wl,-soname,libGL.so.1 -o "$OUT/libGL.so.1"
printf 'Built headless-only compatibility shims in %s\n' "$OUT"
