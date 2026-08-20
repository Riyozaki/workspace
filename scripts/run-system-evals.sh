#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

OUT="${1:-.document-work/evals/system}"
rm -rf "$OUT" .document-work/workflow
mkdir -p "$OUT"

scripts/documentctl doctor --self-test -o "$OUT/doctor.json"
scripts/documentctl workflow examples/workflows/document-suite.json --work-dir "$OUT/workflow" \
  > "$OUT/workflow-result.json"

scripts/documentctl compare \
  .document-work/workflow/operational-report.pdf \
  .document-work/workflow/operational-report.pdf \
  --visual --visual-dir "$OUT/identity-diff" \
  -o "$OUT/compare.json"
scripts/documentctl batch .document-work/workflow \
  --action inspect --workers 4 --output-dir "$OUT/batch" \
  > "$OUT/batch-result.json"
scripts/documentctl xlsx-formulas .document-work/workflow/operational-dashboard.xlsx \
  -o "$OUT/formulas.json"
for format in docx xlsx pptx pdf; do
  case "$format" in
    docx) file=.document-work/workflow/operational-review.docx ;;
    xlsx) file=.document-work/workflow/operational-dashboard.xlsx ;;
    pptx) file=.document-work/workflow/operational-review.pptx ;;
    pdf)  file=.document-work/workflow/operational-report.pdf ;;
  esac
  scripts/documentctl citations "$file" -o "$OUT/citations-$format.json"
done
cat > "$OUT/lineage-plan.json" <<JSON
{
  "claims": [
    {
      "id": "reporting-year",
      "value": "2026",
      "sources": [
        {"path": "$ROOT/.document-work/workflow/operational-dashboard.xlsx", "query": "2026"}
      ],
      "targets": [
        {"path": "$ROOT/.document-work/workflow/operational-review.docx", "query": "2026"},
        {"path": "$ROOT/.document-work/workflow/operational-review.pptx", "query": "2026"},
        {"path": "$ROOT/.document-work/workflow/operational-report.pdf", "query": "2026"}
      ]
    }
  ]
}
JSON
scripts/documentctl lineage "$OUT/lineage-plan.json" -o "$OUT/lineage.json"

"$ROOT/.venv/bin/python" - "$OUT" <<'PY'
import json, pathlib, sys
out = pathlib.Path(sys.argv[1])
doctor = json.loads((out / "doctor.json").read_text())
workflow = json.loads((out / "workflow/manifest.json").read_text())
comparison = json.loads((out / "compare.json").read_text())
batch = json.loads((out / "batch/manifest.json").read_text())
formulas = json.loads((out / "formulas.json").read_text())
lineage = json.loads((out / "lineage.json").read_text())
citations = {
    name: json.loads((out / f"citations-{name}.json").read_text())["entry_count"]
    for name in ("docx", "xlsx", "pptx", "pdf")
}
summary = {
    "passed": (
        doctor["self_test"]["passed"]
        and workflow["status"] == "passed"
        and comparison["identical"]
        and batch["status"] == "passed"
        and lineage["passed"]
    ),
    "core_ready": doctor["core_ready"],
    "self_test": doctor["self_test"],
    "workflow_steps": len(workflow["steps"]),
    "workflow_status": workflow["status"],
    "batch_files": batch["files"],
    "batch_workers": batch["workers"],
    "formula_nodes": formulas["graph"]["formula_count"],
    "formula_lint_issues": len(formulas["issues"]),
    "citation_entries": citations,
    "lineage_claims": lineage["claim_count"],
    "identity_visual_pages": len(comparison["visual"]["pages"]),
}
(out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(summary, ensure_ascii=False, indent=2))
if not summary["passed"]:
    raise SystemExit(1)
PY
