"""Aggregate measured results: quality gaps with 95% CI, speedups with spread, Amdahl decomposition."""
import csv
import json
from collections import defaultdict
from pathlib import Path
import sys

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"


def mean_ci(x):
    x = np.asarray(x, dtype=float)
    n = len(x)
    m = float(x.mean())
    sd = float(x.std(ddof=1)) if n > 1 else 0.0
    if n > 1:
        h = float(stats.t.ppf(0.975, n - 1) * sd / np.sqrt(n))
    else:
        h = 0.0
    return m, sd, h, n


def main():
    sel = json.loads((RES / "selection.json").read_text())
    chosen = sel["chosen_width"]
    with open(RES / "test_metrics.csv") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in ("test_acc", "val_acc", "test_macro_f1", "test_ece", "flops_ratio_vs_teacher"):
            r[k] = float(r[k])
        r["seed"] = int(r["seed"])

    teachers = {r["seed"]: r for r in rows if r["kind"] == "baseline"}
    method = {r["seed"]: r for r in rows if r["kind"] == "method" and r["width"] == chosen}
    seeds = sorted(set(teachers) & set(method))
    gaps = [100 * (teachers[s]["test_acc"] - method[s]["test_acc"]) for s in seeds]
    accs_t = [teachers[s]["test_acc"] for s in seeds]
    accs_s = [method[s]["test_acc"] for s in seeds]
    gm, gsd, gh, gn = mean_ci(gaps)
    tm, tsd, th, _ = mean_ci(accs_t)
    sm, ssd, sh, _ = mean_ci(accs_s)
    f1_t = float(np.mean([teachers[s]["test_macro_f1"] for s in seeds]))
    f1_s = float(np.mean([method[s]["test_macro_f1"] for s in seeds]))
    ece_t = float(np.mean([teachers[s]["test_ece"] for s in seeds]))
    ece_s = float(np.mean([method[s]["test_ece"] for s in seeds]))

    # ---------------- timings
    with open(RES / "timings.csv") as f:
        tim = list(csv.DictReader(f))
    for t in tim:
        for k in ("p1_ms_per_item", "p2_ms_per_item", "p2_iqr_ms", "pre_ms", "fwd_ms"):
            t[k] = float(t[k])
        t["seed"] = int(t["seed"]); t["batch"] = int(t["batch"]); t["flops"] = float(t["flops"])
    by_batch = defaultdict(dict)
    for t in tim:
        by_batch[t["batch"]][(t["seed"], t["name"])] = t

    timing_rows = []
    for batch in (1, 256, 1024):
        for s in seeds:
            # selected student name
            sname = method[s]["name"]
            tb = by_batch[batch].get((s, "teacher"))
            ts = by_batch[batch].get((s, sname))
            if not tb or not ts:
                continue
            timing_rows.append({
                "batch": batch, "seed": s,
                "teacher_p1_ms": tb["p1_ms_per_item"], "student_p1_ms": ts["p1_ms_per_item"],
                "p1_speedup": tb["p1_ms_per_item"] / ts["p1_ms_per_item"],
                "teacher_p2_ms": tb["p2_ms_per_item"], "student_p2_ms": ts["p2_ms_per_item"],
                "p2_speedup": tb["p2_ms_per_item"] / ts["p2_ms_per_item"],
                "teacher_fwd_ms": tb["fwd_ms"], "student_fwd_ms": ts["fwd_ms"],
                "fwd_only_speedup": tb["fwd_ms"] / ts["fwd_ms"],
                "teacher_pre_ms": tb["pre_ms"], "student_pre_ms": ts["pre_ms"],
                "flops_ratio": tb["flops"] / ts["flops"],
                "p2_iqr_student_ms": ts["p2_iqr_ms"],
                "fold_agreement": ts["fold_argmax_agreement"],
                "fold_maxdiff": ts["fold_maxabs_logit_diff"],
            })
    # extra seeds measured only at batch 1024 (same code path)
    extra_p2 = []
    ex_path = RES / "timings_extra.csv"
    if ex_path.exists():
        ex = list(csv.DictReader(open(ex_path)))
        extra_p2 = [float(r["p2_speedup"]) for r in ex]
        extra_p1 = [float(r["p1_speedup"]) for r in ex]
    combined = [r["p2_speedup"] for r in timing_rows if r["batch"] == 1024] + extra_p2
    comb_stats = mean_ci(combined) if combined else (float("nan"),) * 3 + (0,)
    # ---------------- write results.csv (one row per configuration)
    out_rows = []
    out_rows.append({"row": "baseline_teacher", "n_runs": gn,
                     "test_acc_mean": tm, "test_acc_sd": tsd, "test_acc_ci95": th,
                     "macro_f1": f1_t, "ece": ece_t,
                     "flops_per_sample": teachers[seeds[0]]["flops"],
                     "params": teachers[seeds[0]]["params"],
                     "flops_ratio": 1.0, "speedup_batch1024_P2": 1.0,
                     "speedup_batch1024_P1": 1.0, "speedup_batch1_P2": 1.0,
                     "speedup_batch256_P2": 1.0})
    for batch_key, label in ((1024, "speedup_batch1024_P2"), (1024, "speedup_batch1024_P1"),
                             (1, "speedup_batch1_P2"), (256, "speedup_batch256_P2")):
        pass
    def sp(batch, key):
        vals = [r[key] for r in timing_rows if r["batch"] == batch]
        m, sd, h, n = mean_ci(vals) if vals else (float("nan"),) * 3 + (0,)
        return m, sd, h, n
    s1024_p2 = sp(1024, "p2_speedup"); s1024_p1 = sp(1024, "p1_speedup")
    s256_p2 = sp(256, "p2_speedup"); s1_p2 = sp(1, "p2_speedup"); s1024_f = sp(1024, "fwd_only_speedup")
    out_rows[0].update({"speedup_batch1024_P2": 1.0, "speedup_batch256_P2": 1.0,
                        "speedup_batch1_P2": 1.0, "speedup_batch1024_P1": 1.0})
    out_rows.append({"row": "method_distillprune", "n_runs": gn,
                     "test_acc_mean": sm, "test_acc_sd": ssd, "test_acc_ci95": sh,
                     "macro_f1": f1_s, "ece": ece_s,
                     "flops_per_sample": method[seeds[0]]["flops"],
                     "params": method[seeds[0]]["params"],
                     "flops_ratio": method[seeds[0]]["flops_ratio_vs_teacher"],
                     "speedup_batch1024_P2": s1024_p2[0], "speedup_batch1024_P2_sd": s1024_p2[1],
                     "speedup_batch1024_P2_ci95": s1024_p2[2],
                     "speedup_batch1024_P1": s1024_p1[0], "speedup_batch1024_P1_sd": s1024_p1[1],
                     "speedup_batch256_P2": s256_p2[0], "speedup_batch1_P2": s1_p2[0],
                     "speedup_forward_only_batch1024": s1024_f[0],
                     "gap_pp_mean": gm, "gap_pp_sd": gsd, "gap_pp_ci95": gh,
                     "speedup_n_runs_b1024": comb_stats[3],
                     "speedup_b1024_P2_all_seeds": round(comb_stats[0], 4),
                     "speedup_b1024_P2_all_seeds_ci95": round(comb_stats[2], 4)})
    keys = sorted({k for r in out_rows for k in r})
    with open(RES / "results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader(); w.writerows(out_rows)

    # ---------------- ablations table (test)
    abl = defaultdict(list)
    for r in rows:
        if r["kind"] in ("hard_scratch", "distill_scratch", "ablation_prune_only",
                         "ablation_random_prune"):
            abl[r["kind"]].append(r["test_acc"])
    abl_summary = {k: {"mean": float(np.mean(v)), "sd": float(np.std(v, ddof=1)) if len(v) > 1 else 0.0,
                       "n": len(v)} for k, v in abl.items()}

    # ---------------- Amdahl using measured components at batch 1024
    amdahl = []
    for r in timing_rows:
        if r["batch"] != 1024:
            continue
        p1_bound = (r["teacher_fwd_ms"] + r["teacher_pre_ms"]) / (r["student_fwd_ms"] + r["student_pre_ms"])
        p2_ceiling = r["teacher_fwd_ms"] / r["student_fwd_ms"]
        amdahl.append({"seed": r["seed"],
                       "measured_P1_speedup": r["p1_speedup"],
                       "P1_amdahl_bound_pre_plus_fwd": p1_bound,
                       "measured_P2_speedup": r["p2_speedup"],
                       "P2_preprocessing_free_ceiling": p2_ceiling,
                       "share_of_P1_accounted_by_preprocessing": r["student_pre_ms"] /
                           (r["student_fwd_ms"] + r["student_pre_ms"])})
    summary = {
        "chosen_width": chosen, "n_seeds": gn, "seeds": seeds,
        "baseline_test_acc": {"mean": tm, "sd": tsd, "ci95": th},
        "method_test_acc": {"mean": sm, "sd": ssd, "ci95": sh},
        "gap_pp": {"mean": gm, "sd": gsd, "ci95": gh, "per_seed": gaps},
        "speedup": {"batch1024_P2": s1024_p2, "batch1024_P1": s1024_p1,
                    "batch256_P2": s256_p2, "batch1_P2": s1_p2,
                    "forward_only_batch1024": s1024_f},
        "speedup_batch1024_P2_all_seeds": {"mean": comb_stats[0], "sd": comb_stats[1],
                                           "ci95": comb_stats[2], "n": comb_stats[3],
                                           "seeds": [r["seed"] for r in timing_rows if r["batch"] == 1024] + [3, 4][:len(extra_p2)]},
        "flops_ratio": method[seeds[0]]["flops_ratio_vs_teacher"],
        "ablations_test_acc": abl_summary,
        "amdahl": amdahl,
        "timing_rows": timing_rows,
    }
    (RES / "summary.json").write_text(json.dumps(summary, indent=2))

    print("=== QUALITY (test, n=%d seeds) ===" % gn)
    print(f"baseline {tm:.4f} ± {th:.4f} (sd {tsd:.4f})")
    print(f"method   {sm:.4f} ± {sh:.4f} (sd {ssd:.4f})")
    print(f"paired gap {gm:+.3f} pp (sd {gsd:.3f}, 95% CI ±{gh:.3f})")
    print(f"macro-F1: baseline {f1_t:.4f} -> method {f1_s:.4f}; ECE: {ece_t:.4f} -> {ece_s:.4f}")
    print("\n=== SPEED ===")
    print(f"FLOPs ratio {method[seeds[0]]['flops_ratio_vs_teacher']:.2f}x")
    for name, v in (("P2 batch 1024", s1024_p2), ("P1 batch 1024", s1024_p1),
                    ("P2 batch 256", s256_p2), ("P2 batch 1", s1_p2),
                    ("forward only b1024", s1024_f)):
        print(f"{name:20s}: {v[0]:.2f}x  sd {v[1]:.2f}  ci95 ±{v[2]:.2f}  (n={v[3]})")
    print(f"P2 batch 1024, all seeds: {comb_stats[0]:.2f}x sd {comb_stats[1]:.2f} "
          f"ci95 ±{comb_stats[2]:.2f} (n={comb_stats[3]})")
    print("\n=== AMDAHL (batch 1024, measured components) ===")
    for a in amdahl:
        print(f"seed {a['seed']}: P1 measured {a['measured_P1_speedup']:.2f}x "
              f"(Amdahl bound {a['P1_amdahl_bound_pre_plus_fwd']:.2f}x, preprocessing share "
              f"{100*a['share_of_P1_accounted_by_preprocessing']:.0f}%); "
              f"P2 measured {a['measured_P2_speedup']:.2f}x "
              f"(preprocessing-free ceiling {a['P2_preprocessing_free_ceiling']:.2f}x)")
    print("\n=== ABLATIONS (test accuracy, mean over seeds) ===")
    for k, v in abl_summary.items():
        print(f"{k:24s} {v['mean']:.4f} (sd {v['sd']:.4f}, n={v['n']})")
    print("\nwrote results.csv, summary.json")


if __name__ == "__main__":
    main()
