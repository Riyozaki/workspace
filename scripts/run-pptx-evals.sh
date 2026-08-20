#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

OUT="${1:-.document-work/evals/pptx}"
rm -rf "$OUT"
mkdir -p "$OUT"

DECK="$OUT/operational-review.pptx"
UPDATED="$OUT/operational-review-updated.pptx"

scripts/documentctl pptx-create examples/pptx/operational-review.json "$DECK" \
  --expected-slides 9 --require-notes > "$OUT/create-result.json"
scripts/documentctl inspect "$DECK" -o "$OUT/inspection.json"
scripts/documentctl pptx-edit "$DECK" "$UPDATED" --plan examples/pptx/review-plan.json \
  > "$OUT/edit-result.json"
scripts/documentctl pptx-validate "$UPDATED" \
  --expected-slides 9 --require-notes \
  --require-text "три команды" --require-text "7 ноября" \
  -o "$OUT/qa.json"

if scripts/documentctl env >/dev/null 2>&1; then
  scripts/documentctl pptx-validate "$UPDATED" \
    --expected-slides 9 --require-notes --render --render-dir "$OUT/render" --timeout 120 \
    --require-text "три команды" --require-text "7 ноября" \
    -o "$OUT/qa-with-render.json"
  render_status="passed"
else
  render_status="skipped: soffice unavailable"
fi

"$ROOT/.venv/bin/python" - "$OUT" "$render_status" <<'PY'
import json, pathlib, sys
out = pathlib.Path(sys.argv[1])
qa = json.loads((out / "qa.json").read_text())
deck = qa["presentation"]
summary = {
    "passed": qa["passed"],
    "qa": qa["summary"],
    "render": sys.argv[2],
    "slides": deck["totals"]["slides"],
    "charts": deck["totals"]["charts"],
    "tables": deck["totals"]["tables"],
    "notes_slides": deck["totals"]["notes_slides"],
    "output": str(out / "operational-review-updated.pptx"),
}
(out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(summary, ensure_ascii=False, indent=2))
PY
