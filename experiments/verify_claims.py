"""Verify that the headline numbers written in report.md/README.md match the computed artifacts.

Fails loudly if the documents and results/summary.json diverge (a common source of inflated or stale
claims). Run: python experiments/verify_claims.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"


def main():
    s = json.loads((RES / "summary.json").read_text())
    gap = s["gap_pp"]
    acc_b = s["baseline_test_acc"]["mean"] * 100
    acc_m = s["method_test_acc"]["mean"] * 100
    sp3 = s["speedup"]["batch1024_P2"]
    sp5 = s["speedup_batch1024_P2_all_seeds"]
    p1 = s["speedup"]["batch1024_P1"][0]
    report = (ROOT / "report.md").read_text()
    readme = (ROOT / "README.md").read_text()
    errs = []

    def need(text, needle, label):
        if needle not in text:
            errs.append(f"{label}: '{needle}' not found")

    need(report, f"{acc_b:.2f}%", "baseline accuracy")
    need(report, f"{acc_m:.2f}%", "method accuracy")
    need(report, f"{gap['mean']:.3f}", "mean gap")
    need(report, f"{gap['mean'] + gap['ci95']:.3f}", "gap CI upper")
    need(report, f"{sp5['mean']:.2f}×", "speedup n=5")
    need(report, f"{sp3[0]:.2f}×", "speedup n=3")
    need(report, f"{p1:.2f}×", "P1 speedup")
    need(readme, f"{sp5['mean']:.2f}×", "README speedup")
    need(readme, f"{abs(gap['mean']):.2f} pp", "README gap")

    # the exploratory claim must be labelled post-hoc in both documents
    if "EXPLORATORY" not in report:
        errs.append("report: exploratory section missing")
    if "post-hoc" not in readme and "Post-hoc" not in readme:
        errs.append("README: exploratory result not labelled post-hoc")

    if errs:
        print("FAILED claim checks:")
        for e in errs:
            print(" -", e)
        sys.exit(1)
    print("All headline numbers in report.md/README.md match results/summary.json:")
    print(f"  acc {acc_b:.2f}% -> {acc_m:.2f}%  gap {gap['mean']:.3f} pp "
          f"(CI upper {gap['mean'] + gap['ci95']:.3f})")
    print(f"  speedup b1024: {sp3[0]:.2f}x (n=3), {sp5['mean']:.2f}x (n=5); P1 {p1:.2f}x")


if __name__ == "__main__":
    main()
