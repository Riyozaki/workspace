#!/usr/bin/env bash
# End-to-end DOCX vertical-slice evaluation. Outputs stay outside Git by default.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

OUT="${1:-.document-work/evals/docx}"
rm -rf "$OUT"
mkdir -p "$OUT"

DOC="$OUT/operational-review.docx"
REDLINED="$OUT/operational-review-redlined.docx"

scripts/documentctl create examples/docx/operational-review.json "$DOC" \
  --require-header --require-footer --require-page-numbers --require-toc --require-images 1 \
  > "$OUT/create-result.json"

scripts/documentctl inspect "$DOC" --include-text -o "$OUT/inspection.json"
scripts/documentctl extract "$DOC" --format text -o "$OUT/content.txt"

scripts/documentctl edit "$DOC" "$REDLINED" --plan examples/docx/review-plan.json \
  > "$OUT/edit-result.json"

scripts/documentctl validate "$REDLINED" \
  --require-header --require-footer --require-page-numbers --require-toc --require-images 1 \
  --expect-text "через 20 рабочих дней" --forbid-text "{{" --forbid-text "TODO" \
  -o "$OUT/qa.json"

scripts/documentctl diff "$DOC" "$REDLINED" -o "$OUT/diff.json"
scripts/documentctl docx-tracked-check "$DOC" "$REDLINED" -o "$OUT/tracked-proof.json"
scripts/documentctl docx-revisions "$REDLINED" "$OUT/operational-review-accepted.docx" \
  --mode accept > "$OUT/accept-result.json"

if scripts/documentctl env >/dev/null 2>&1; then
  scripts/documentctl validate "$DOC" \
    --render --render-dir "$OUT/render" --timeout 120 \
    --require-header --require-footer --require-page-numbers --require-toc --require-images 1 \
    -o "$OUT/qa-with-render.json"
  render_status="passed"
else
  render_status="skipped: soffice unavailable"
fi

"$ROOT/.venv/bin/python" - "$OUT" "$render_status" <<'PY'
import json, pathlib, sys
out = pathlib.Path(sys.argv[1])
qa = json.loads((out / "qa.json").read_text())
diff = json.loads((out / "diff.json").read_text())
tracked = json.loads((out / "tracked-proof.json").read_text())
summary = {
    "passed": qa["passed"] and tracked["passed"],
    "qa": qa["summary"],
    "schema": qa["schema"],
    "render": sys.argv[2],
    "tracked_completeness": tracked["passed"],
    "changed_parts": diff["package"]["changed_parts"],
    "added_parts": diff["package"]["added_parts"],
    "outputs": {
        "created": str(out / "operational-review.docx"),
        "redlined": str(out / "operational-review-redlined.docx"),
    },
}
(out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(summary, ensure_ascii=False, indent=2))
PY
