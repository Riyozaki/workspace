#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="${1:-.document-work/evals/all}"
rm -rf "$OUT"
mkdir -p "$OUT"

CURRENT_PID=""
collect_descendants() {
  local parent="$1" child
  while read -r child; do
    [[ -n "$child" ]] || continue
    collect_descendants "$child"
  done < <(pgrep -P "$parent" 2>/dev/null || true)
  printf '%s\n' "$parent"
}
cleanup_current_suite() {
  [[ -n "$CURRENT_PID" ]] || return 0
  local pids
  pids="$(collect_descendants "$CURRENT_PID")"
  # Kill leaves before parents, including WASM workers that create a new session.
  while read -r pid; do kill -TERM "$pid" 2>/dev/null || true; done <<< "$pids"
  sleep 0.5
  while read -r pid; do kill -KILL "$pid" 2>/dev/null || true; done <<< "$pids"
}
trap cleanup_current_suite INT TERM EXIT

run_suite() {
  local index="$1" label="$2" script="$3" subdir="$4"
  local log="$OUT/$subdir.log" started elapsed status
  started=$SECONDS
  printf '[%s/5] %s...\n' "$index" "$label"
  "$script" "$OUT/$subdir" > "$log" 2>&1 &
  CURRENT_PID=$!
  if wait "$CURRENT_PID"; then
    status=0
  else
    status=$?
  fi
  CURRENT_PID=""
  elapsed=$((SECONDS - started))
  if [[ "$status" -ne 0 ]]; then
    printf '[%s/5] %s: FAILED after %ss (last log lines follow)\n' "$index" "$label" "$elapsed" >&2
    tail -n 40 "$log" >&2 || true
    return "$status"
  fi
  printf '[%s/5] %s: passed in %ss\n' "$index" "$label" "$elapsed"
}

run_suite 1 DOCX scripts/run-docx-evals.sh docx
run_suite 2 XLSX scripts/run-xlsx-evals.sh xlsx
run_suite 3 PPTX scripts/run-pptx-evals.sh pptx
run_suite 4 PDF scripts/run-pdf-evals.sh pdf
run_suite 5 SYSTEM scripts/run-system-evals.sh system

"$ROOT/.venv/bin/python" - "$OUT" <<'PY'
import json, pathlib, sys
out = pathlib.Path(sys.argv[1])
paths = {
    "docx": out / "docx/summary.json",
    "xlsx": out / "xlsx/summary.json",
    "pptx": out / "pptx/summary.json",
    "pdf": out / "pdf/summary.json",
    "system": out / "system/summary.json",
}
results = {name: json.loads(path.read_text()) for name, path in paths.items()}
summary = {
    "passed": all(value.get("passed") for value in results.values()),
    "results": results,
}
(out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(summary, ensure_ascii=False, indent=2))
if not summary["passed"]:
    raise SystemExit(1)
PY
