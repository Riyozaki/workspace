"""Single, frozen look at the official test set.

Run only after results/selection.json exists. Computes test metrics for every saved model and the
paired accuracy gap (teacher - student) per seed. No model selection happens here.
"""
import csv
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.data import load_fashion
from src.mlp import MLP, count_params, evaluate, forward_flops_per_sample

RES = ROOT / "results"
MODELS = RES / "models"


def load_model(path: Path) -> MLP:
    z = np.load(path)
    n_layers = sum(1 for k in z.files if k.startswith("W"))
    sizes = [z[f"W{i}"].shape[0] for i in range(n_layers)] + [z[f"W{n_layers-1}"].shape[1]]
    m = MLP(sizes, dropout=0.0)
    m.W = [z[f"W{i}"].copy() for i in range(n_layers)]
    m.b = [z[f"b{i}"].copy() for i in range(n_layers)]
    return m


def main() -> None:
    sel = json.loads((RES / "selection.json").read_text())
    d = load_fashion()
    rows = []
    for meta_path in sorted(MODELS.glob("*.json")):
        meta = json.loads(meta_path.read_text())
        model = load_model(meta_path.with_suffix(".npz"))
        v = evaluate(model, d["x_test"], d["y_test"])
        rows.append({
            "seed": meta["seed"], "name": meta["name"], "kind": meta["kind"],
            "width": meta["width"], "val_acc": meta["val_acc"], "test_acc": v["acc"],
            "test_macro_f1": v["macro_f1"], "test_ece": v["ece"],
            "params": count_params(model), "flops": forward_flops_per_sample(model),
            "flops_ratio_vs_teacher": meta.get("flops_ratio_vs_teacher", 1.0),
            "train_wall_s": meta.get("train_wall_s"),
            "selected": (meta["kind"] == "method" and meta["width"] == sel["chosen_width"]),
            "control_for_selected": (meta["kind"] in ("hard_scratch", "distill_scratch")
                                     and meta["width"] == sel["chosen_width"]),
        })
    out = RES / "test_metrics.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    # paired gaps for the selected configuration
    teachers = {r["seed"]: r["test_acc"] for r in rows if r["kind"] == "baseline"}
    sel_rows = [r for r in rows if r["selected"]]
    for r in sel_rows:
        r["test_gap_pp"] = 100 * (teachers[r["seed"]] - r["test_acc"])
    print(f"wrote {out} ({len(rows)} models)")
    print("selected width:", sel["chosen_width"])
    for r in sel_rows:
        print(f"seed {r['seed']}: teacher {teachers[r['seed']]:.4f} -> student {r['test_acc']:.4f} "
              f"(gap {r['test_gap_pp']:+.2f} pp, {r['flops_ratio_vs_teacher']:.1f}x FLOPs)")
    gaps = [r["test_gap_pp"] for r in sel_rows]
    if gaps:
        print(f"mean gap {np.mean(gaps):+.2f} pp, sd {np.std(gaps, ddof=1) if len(gaps)>1 else 0:.2f}")
        (RES / "selected_gaps.json").write_text(json.dumps(
            {"gaps_pp": gaps, "mean": float(np.mean(gaps)),
             "sd": float(np.std(gaps, ddof=1)) if len(gaps) > 1 else 0.0}, indent=2))


if __name__ == "__main__":
    main()
