#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="${1:-.model-work/evals/modeling}"
rm -rf "$OUT"
mkdir -p "$OUT"

MODEL="$OUT/lounge-chair.glb"
OPTIMIZED="$OUT/lounge-chair-optimized.glb"

scripts/modelctl create examples/modeling/lounge-chair.json "$MODEL" \
  --backend blender -o "$OUT/create.json"
scripts/modelctl validate "$MODEL" --profile render --strict --max-triangles 100000 \
  -o "$OUT/qa.json"
scripts/modelctl render "$MODEL" -o "$OUT/render" \
  --resolution 384 --samples 8 --views perspective front right back \
  > "$OUT/render-command.json"
scripts/modelctl optimize "$MODEL" "$OPTIMIZED" --compression none \
  -o "$OUT/optimize.json"
scripts/modelctl validate "$OPTIMIZED" --profile web --strict --max-triangles 100000 \
  -o "$OUT/optimized-qa.json"
scripts/modelctl viewer "$OPTIMIZED" -o "$OUT/viewer" \
  --title "Verified lounge chair" > "$OUT/viewer-command.json"

"$ROOT/.venv/bin/python" - "$OUT" <<'PY'
import json, pathlib, sys
out = pathlib.Path(sys.argv[1])
created = json.loads((out / "create.json").read_text())
qa = json.loads((out / "qa.json").read_text())
render = json.loads((out / "render/render-report.json").read_text())
optimized = json.loads((out / "optimize.json").read_text())
optimized_qa = json.loads((out / "optimized-qa.json").read_text())
scene = qa["inspection"]["scene"]
summary = {
    "passed": created["passed"] and qa["passed"] and optimized_qa["passed"] and not render["summary"]["blank_views"],
    "backend": created["build"]["backend"],
    "blender": created["build"].get("blender"),
    "gltf_valid": qa["gltf_validator"]["valid"],
    "qa": qa["summary"],
    "objects": scene["geometry_instances"],
    "triangles": scene["triangles"],
    "materials": scene["materials"],
    "views": len(render["views"]),
    "blank_views": render["summary"]["blank_views"],
    "optimized_bytes": optimized["output_bytes"],
    "viewer": str(out / "viewer/index.html"),
    "model": str(out / "lounge-chair.glb"),
    "contact_sheet": str(out / "render/contact-sheet.png"),
}
(out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(summary, ensure_ascii=False, indent=2))
if not summary["passed"]:
    raise SystemExit(1)
PY
