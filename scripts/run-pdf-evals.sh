#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

OUT="${1:-.document-work/evals/pdf}"
rm -rf "$OUT"
mkdir -p "$OUT"

SOURCE="$OUT/operational-report.pdf"
TRANSFORMED="$OUT/operational-report-draft.pdf"
FINAL="$OUT/operational-report-reviewed.pdf"

scripts/documentctl pdf-create examples/pdf/operational-report.json "$SOURCE" \
  --render --render-dir "$OUT/source-render" > "$OUT/create-result.json"
scripts/documentctl pdf-extract "$SOURCE" --tables -o "$OUT/extraction.json"

cat > "$OUT/transform.json" <<'JSON'
{
  "inputs": [{"path": "operational-report.pdf", "pages": "all"}],
  "watermark": {"text": "DRAFT", "font_size": 42, "color": "808080", "opacity": 0.10, "angle": 35},
  "metadata": {"title": "Операционный отчёт — проект"}
}
JSON
scripts/documentctl pdf-transform "$OUT/transform.json" "$TRANSFORMED" > "$OUT/transform-result.json"

cat > "$OUT/overlay.json" <<'JSON'
{
  "items": [
    {"page": 4, "type": "text", "x": 360, "y": 690, "width": 150, "height": 18, "text": "ПРОВЕРЕНО", "font_size": 9, "color": "26734D", "align": "right"},
    {"page": 4, "type": "check", "x": 520, "y": 687, "width": 12, "height": 12, "color": "26734D"}
  ]
}
JSON
scripts/documentctl pdf-overlay "$TRANSFORMED" "$FINAL" --plan "$OUT/overlay.json" > "$OUT/overlay-result.json"
scripts/documentctl pdf-validate "$FINAL" \
  --expected-pages 4 --require-text "7 ноября" --require-text "ПРОВЕРЕНО" \
  --render --render-dir "$OUT/final-render" -o "$OUT/qa.json"
scripts/documentctl pdf-ocr "$SOURCE" "$OUT/operational-report-ocr.pdf" \
  --language rus+eng --dpi 180 > "$OUT/ocr-result.json"
scripts/documentctl pdf-validate "$OUT/operational-report-ocr.pdf" \
  --expected-pages 4 --require-text "Операционный" \
  -o "$OUT/ocr-qa.json"

"$ROOT/.venv/bin/python" - "$OUT" <<'PY'
import json, pathlib, sys
out = pathlib.Path(sys.argv[1])
qa = json.loads((out / "qa.json").read_text())
extracted = json.loads((out / "extraction.json").read_text())
ocr = json.loads((out / "ocr-result.json").read_text())
ocr_qa = json.loads((out / "ocr-qa.json").read_text())
summary = {
    "passed": qa["passed"] and ocr_qa["passed"],
    "qa": qa["summary"],
    "pages": qa["pdf"]["page_count"],
    "tables": len(extracted["tables"]),
    "forms": extracted["form_field_count"],
    "fonts_unembedded": qa["pdf"]["unembedded_fonts"],
    "render_pages": qa["render"]["page_count"],
    "ocr_engine": ocr["engine"],
    "ocr_pages": ocr["pages"],
    "output": str(out / "operational-report-reviewed.pdf"),
}
(out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(summary, ensure_ascii=False, indent=2))
PY
