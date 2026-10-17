"""Ablations at the frozen student width:
  1) prune-only (no fine-tuning at all)          -> shows what distillation fine-tuning buys
  2) random-prune + distillation (same budget)   -> shows that the importance criterion matters
Validation metrics only; test is evaluated later by evaluate_test.py.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.data import load_fashion
from src.mlp import (MLP, count_params, distillation_targets, evaluate,
                     forward_flops_per_sample, prune_teacher_random, train)

RES = ROOT / "results"
MODELS = RES / "models"
CFG = json.loads((RES / "frozen_config.json").read_text())
SEL = json.loads((RES / "selection.json").read_text())
W1, W2 = (int(x) for x in SEL["chosen_width"].split("-"))
STUDENT_EPOCHS = 30
T, ALPHA = 4.0, 0.5


def load_model(path):
    z = np.load(path)
    n = sum(1 for k in z.files if k.startswith("W"))
    sizes = [z[f"W{i}"].shape[0] for i in range(n)] + [z[f"W{n-1}"].shape[1]]
    m = MLP(sizes, dropout=0.0)
    m.W = [z[f"W{i}"].copy() for i in range(n)]
    m.b = [z[f"b{i}"].copy() for i in range(n)]
    return m


def save(model, name, meta):
    payload = {f"W{i}": w for i, w in enumerate(model.W)}
    payload.update({f"b{i}": b for i, b in enumerate(model.b)})
    np.savez_compressed(MODELS / f"{name}.npz", **payload)
    (MODELS / f"{name}.json").write_text(json.dumps(meta, indent=2))


def main():
    d = load_fashion()
    seeds = sorted({int(json.loads(p.read_text())["seed"])
                    for p in MODELS.glob("seed*_teacher.json")})
    out = open(RES / "ablations.jsonl", "a")
    for seed in seeds:
        teacher = load_model(MODELS / f"seed{seed}_teacher.npz")
        print(f"seed {seed}", flush=True)
        # 1) prune only, no fine-tuning
        from src.mlp import prune_teacher
        pruned = prune_teacher(teacher, W1, W2)
        v = evaluate(pruned, d["x_val"], d["y_val"])
        rec = {"seed": seed, "name": f"prune_only_{W1}x{W2}", "kind": "ablation_prune_only",
               "width": f"{W1}-{W2}", "val_acc": v["acc"], "val_f1": v["macro_f1"],
               "val_ece": v["ece"], "params": count_params(pruned),
               "flops": forward_flops_per_sample(pruned),
               "flops_ratio_vs_teacher": forward_flops_per_sample(teacher) / forward_flops_per_sample(pruned),
               "train_wall_s": 0.0, "epochs": 0}
        print("  prune_only", f"{v['acc']:.4f}", flush=True)
        save(pruned, f"seed{seed}_prune_only_{W1}x{W2}", rec)
        out.write(json.dumps(rec) + "\n"); out.flush()
        # 2) random pruning + same distillation budget
        soft = distillation_targets(teacher, d["x_train"], T)
        rand = prune_teacher_random(teacher, W1, W2, seed)
        t0 = time.time()
        hist = train(rand, d["x_train"], d["y_train"], epochs=STUDENT_EPOCHS,
                     lr=CFG["student_lr"], weight_decay=1e-4, soft_targets=soft,
                     alpha=ALPHA, temperature=T, x_val=d["x_val"], y_val=d["y_val"],
                     seed=seed + 100)
        v = evaluate(rand, d["x_val"], d["y_val"])
        rec = {"seed": seed, "name": f"randomprune_dst_{W1}x{W2}", "kind": "ablation_random_prune",
               "width": f"{W1}-{W2}", "val_acc": v["acc"], "val_f1": v["macro_f1"],
               "val_ece": v["ece"], "params": count_params(rand),
               "flops": forward_flops_per_sample(rand),
               "flops_ratio_vs_teacher": forward_flops_per_sample(teacher) / forward_flops_per_sample(rand),
               "train_wall_s": time.time() - t0, "epochs": STUDENT_EPOCHS,
               "val_curve": [h["val_acc"] for h in hist]}
        print("  randomprune", f"{v['acc']:.4f}", flush=True)
        save(rand, f"seed{seed}_randomprune_dst_{W1}x{W2}", rec)
        out.write(json.dumps(rec) + "\n"); out.flush()
    out.close()
    print("done")


if __name__ == "__main__":
    main()
