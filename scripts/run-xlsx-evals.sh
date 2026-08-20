#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

OUT="${1:-.document-work/evals/xlsx}"
rm -rf "$OUT"
mkdir -p "$OUT"

DRAFT="$OUT/operational-dashboard-draft.xlsx"
EDITED="$OUT/operational-dashboard-scenario.xlsx"
FINAL="$OUT/operational-dashboard.xlsx"

scripts/documentctl xlsx-create examples/xlsx/operational-dashboard.json "$DRAFT" \
  --require-sheet Панель --require-sheet Данные --require-sheet Допущения \
  --require-cell 'Панель!B5' --require-cell 'Допущения!B2' --require-formulas \
  > "$OUT/create-result.json"

scripts/documentctl inspect "$DRAFT" -o "$OUT/inspection.json"
scripts/documentctl xlsx-edit "$DRAFT" "$EDITED" --plan examples/xlsx/scenario-update.json \
  > "$OUT/edit-result.json"

scripts/documentctl xlsx-validate "$EDITED" \
  --require-sheet Панель --require-sheet Данные --require-sheet Допущения \
  --require-cell 'Панель!B5' --require-cell 'Допущения!B2' --require-formulas \
  -o "$OUT/qa-before-recalc.json"

if scripts/documentctl env >/dev/null 2>&1; then
  scripts/documentctl xlsx-recalc "$EDITED" "$FINAL" --timeout 120 > "$OUT/recalc-result.json"
  scripts/documentctl xlsx-validate "$FINAL" \
    --require-sheet Панель --require-sheet Данные --require-sheet Допущения \
    --require-cell 'Панель!B5' --require-cell 'Допущения!B2' \
    --require-formulas --require-recalculated --render --render-dir "$OUT/render" --timeout 120 \
    -o "$OUT/qa.json"
  recalc_status="passed"
else
  cp "$EDITED" "$FINAL"
  cp "$OUT/qa-before-recalc.json" "$OUT/qa.json"
  recalc_status="skipped: soffice unavailable"
fi

"$ROOT/.venv/bin/python" - "$OUT" "$recalc_status" <<'PY'
import json, pathlib, sys
out = pathlib.Path(sys.argv[1])
qa = json.loads((out / "qa.json").read_text())
inspection = json.loads((out / "inspection.json").read_text())["semantic"]
summary = {
    "passed": qa["passed"],
    "qa": qa["summary"],
    "recalculation": sys.argv[2],
    "sheets": inspection["sheet_names"],
    "formulas": inspection["totals"].get("formulas", 0),
    "tables": inspection["totals"].get("tables", 0),
    "charts": inspection["totals"].get("charts", 0),
    "output": str(out / "operational-dashboard.xlsx"),
}
(out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(summary, ensure_ascii=False, indent=2))
PY
