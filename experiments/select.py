"""Freeze the student width using VALIDATION ONLY (pre-registered rule). Test data is not read."""
import json
from collections import defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"

def main() -> None:
    runs = [json.loads(l) for l in (RES / "runs.jsonl").read_text().splitlines() if l.strip()]
    teachers = {r["seed"]: r for r in runs if r["kind"] == "baseline"}
    methods = [r for r in runs if r["kind"] == "method"]
    by_width = defaultdict(dict)
    for r in methods:
        if r["seed"] in teachers:
            by_width[r["width"]][r["seed"]] = r
    report = {}
    for width, per_seed in by_width.items():
        gaps = [teachers[s]["val_acc"] - r["val_acc"] for s, r in per_seed.items()]
        ratio = next(iter(per_seed.values()))["flops_ratio_vs_teacher"]
        report[width] = {"mean_val_gap_pp": 100 * sum(gaps) / len(gaps),
                         "max_val_gap_pp": 100 * max(gaps),
                         "n": len(gaps), "flops_ratio": ratio}
    # pre-registered rule: smallest width with mean val gap <= 0.5 pp and >=10x FLOPs
    def width_key(w):
        return int(w.split("-")[0])
    eligible = {w: r for w, r in report.items() if r["flops_ratio"] >= 10.0}
    ok = {w: r for w, r in eligible.items() if r["mean_val_gap_pp"] <= 0.5}
    if ok:
        chosen = min(ok, key=width_key)
        reason = "smallest width with val gap <= 0.5pp and >=10x FLOPs"
    else:
        chosen = min(eligible, key=lambda w: eligible[w]["mean_val_gap_pp"])
        reason = "no width met 0.5pp; took highest-validation-accuracy width with >=10x FLOPs"
    out = {"chosen_width": chosen, "reason": reason, "by_width": report,
           "selection_data": "validation split only", "n_seeds": len(teachers)}
    (RES / "selection.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
