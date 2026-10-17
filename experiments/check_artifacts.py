"""Consistency checks for the reported artifacts (run before submitting)."""
import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"


def fail(msg):
    print("FAIL:", msg)
    sys.exit(1)


def main():
    sel = json.loads((RES / "selection.json").read_text())
    chosen = sel["chosen_width"]
    print("selection:", chosen, "| reason:", sel["reason"])

    rows = list(csv.DictReader(open(RES / "test_metrics.csv")))
    tm = list(csv.DictReader(open(RES / "timings.csv")))
    summ = json.loads((RES / "summary.json").read_text())

    seeds = sorted({int(r["seed"]) for r in rows if r["kind"] == "baseline"})
    print("seeds with teacher:", seeds)
    for s in seeds:
        if not any(r["kind"] == "method" and r["width"] == chosen and int(r["seed"]) == s for r in rows):
            fail(f"seed {s} has no method model at chosen width")

    # 1) every selected row must have val_acc recorded and a matching model file
    for r in rows:
        if r["selected"] == "True":
            p = RES / "models" / f"seed{r['seed']}_distillprune_{chosen.replace('-', 'x')}.npz"
            if not p.exists():
                fail(f"missing model {p}")
    # 2) no NaN in the headline numbers
    for k in ("speedup",):
        for name, tup in summ[k].items():
            if any(isinstance(x, float) and (math.isnan(x) or math.isinf(x)) for x in tup):
                fail(f"NaN/inf in speedup {name}: {tup}")
    # 3) timings must contain teacher and method for every BENCHMARKED seed and batch
    timing_seeds = sorted({int(r["seed"]) for r in tm})
    print("seeds with timings:", timing_seeds)
    if not set(timing_seeds) <= set(seeds):
        fail("timings reference seeds without quality results")
    for s in timing_seeds:
        for b in (1, 256, 1024):
            names = {(int(r["seed"]), r["name"]) for r in tm if int(r["batch"]) == b}
            if (s, "teacher") not in names:
                fail(f"no teacher timing seed {s} batch {b}")
            if (s, f"distillprune_{chosen.replace('-', 'x')}") not in names:
                fail(f"no method timing seed {s} batch {b}")
    # 4) folded pipeline must reproduce explicit normalization exactly
    for r in tm:
        if float(r["fold_argmax_agreement"]) < 1.0:
            fail(f"fold mismatch {r['name']} seed {r['seed']}: {r['fold_argmax_agreement']}")
    # 5) quality gap recomputation must match summary.json
    t = {int(r["seed"]): float(r["test_acc"]) for r in rows if r["kind"] == "baseline"}
    mrows = [r for r in rows if r["selected"] == "True"]
    gaps = [100 * (t[int(r["seed"])] - float(r["test_acc"])) for r in mrows]
    mean_gap = sum(gaps) / len(gaps)
    if abs(mean_gap - summ["gap_pp"]["mean"]) > 1e-9:
        fail(f"gap mismatch: {mean_gap} vs {summ['gap_pp']['mean']}")
    # 6) extra timing seeds + combined speedup consistency
    ex_path = RES / "timings_extra.csv"
    if ex_path.exists():
        ex = list(csv.DictReader(open(ex_path)))
        for r in ex:
            if int(r["seed"]) not in seeds:
                fail(f"extra timing seed {r['seed']} has no quality results")
        by = {(int(r["seed"]), r["name"]): float(r["p2_ms_per_item"])
              for r in tm if int(r["batch"]) == 1024}
        base = [by[(sd, "teacher")] / by[(sd, f"distillprune_{chosen.replace('-', 'x')}")]
                for sd in timing_seeds]
        combined = base + [float(r["p2_speedup"]) for r in ex]
        m = sum(combined) / len(combined)
        got = summ["speedup_batch1024_P2_all_seeds"]["mean"]
        if abs(m - got) > 1e-9:
            fail(f"combined speedup mismatch: {m} vs {got}")
        print(f"combined P2 batch1024 speedup: {m:.3f}x over n={len(combined)} seeds")
    print(f"checks OK: {len(rows)} evaluated models, {len(tm)} timing rows, "
          f"mean gap {mean_gap:.3f} pp, speedup b1024 {summ['speedup']['batch1024_P2'][0]:.2f}x")


if __name__ == "__main__":
    main()
