"""EXPLORATORY (declared after the primary results were known, 13:20 UTC).

Question: does longer distillation fine-tuning (60 instead of 30 epochs) close the quality gap?
This is a post-hoc robustness check, NOT the pre-registered method. All 5 seeds are run; no seed
selection. Results are stored separately in results/exploratory_60ep.jsonl.
"""
import argparse, json, sys, time
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.data import load_fashion
from src.mlp import (MLP, count_params, distillation_targets, evaluate,
                     forward_flops_per_sample, prune_teacher, train)

RES = ROOT / "results"; MODELS = RES / "models"
CFG = json.loads((RES / "frozen_config.json").read_text())
W1, W2, EPOCHS, T, ALPHA = 160, 96, 60, 4.0, 0.5


def load_model(path):
    z = np.load(path); n = sum(1 for k in z.files if k.startswith("W"))
    sizes = [z[f"W{i}"].shape[0] for i in range(n)] + [z[f"W{n-1}"].shape[1]]
    m = MLP(sizes, dropout=0.0); m.W = [z[f"W{i}"].copy() for i in range(n)]
    m.b = [z[f"b{i}"].copy() for i in range(n)]
    return m


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--seeds", default="0,1,2,3,4")
    args = ap.parse_args()
    d = load_fashion()
    for seed in [int(s) for s in args.seeds.split(",")]:
        teacher = load_model(MODELS / f"seed{seed}_teacher.npz")
        soft = distillation_targets(teacher, d["x_train"], T)
        student = prune_teacher(teacher, W1, W2)
        t0 = time.time()
        hist = train(student, d["x_train"], d["y_train"], epochs=EPOCHS, lr=CFG["student_lr"],
                     weight_decay=1e-4, soft_targets=soft, alpha=ALPHA, temperature=T,
                     x_val=d["x_val"], y_val=d["y_val"], seed=seed + 100)
        val = evaluate(student, d["x_val"], d["y_val"])
        test = evaluate(student, d["x_test"], d["y_test"])
        rec = {"seed": seed, "name": f"exploratory_60ep_{W1}x{W2}", "kind": "exploratory_60ep",
               "width": f"{W1}-{W2}", "val_acc": val["acc"], "test_acc": test["acc"],
               "test_macro_f1": test["macro_f1"], "test_ece": test["ece"],
               "params": count_params(student), "flops": forward_flops_per_sample(student),
               "flops_ratio_vs_teacher": forward_flops_per_sample(teacher) / forward_flops_per_sample(student),
               "train_wall_s": time.time() - t0, "epochs": EPOCHS,
               "val_curve": [h["val_acc"] for h in hist]}
        print(json.dumps({k: rec[k] for k in ("seed", "val_acc", "test_acc", "train_wall_s")}), flush=True)
        with open(RES / "exploratory_60ep.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")


if __name__ == "__main__":
    main()
