"""Phase 1: pre-registered baseline grid, selected on VALIDATION ONLY."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data import load_fashion
from src.mlp import MLP, evaluate, train
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results"
OUT.mkdir(exist_ok=True)

if __name__ == "__main__":
    t_start = time.time()
    d = load_fashion()
    print({k: v.shape for k, v in d.items() if hasattr(v, "shape")}, flush=True)
    rows = []
    for lr in (5e-4, 1e-3):
        for dropout in (0.0, 0.2):
            print(f"\n=== lr={lr} dropout={dropout} ===", flush=True)
            rng = np.random.default_rng(0)
            model = MLP([784, 1024, 1024, 10], dropout=dropout, rng=rng)
            hist = train(model, d["x_train"], d["y_train"], epochs=15, lr=lr,
                         weight_decay=1e-4, x_val=d["x_val"], y_val=d["y_val"], seed=0)
            v = evaluate(model, d["x_val"], d["y_val"])
            row = {"lr": lr, "dropout": dropout, "val_acc": v["acc"], "val_f1": v["macro_f1"],
                   "val_ece": v["ece"], "train_wall_s": hist[-1]["wall_s"],
                   "per_epoch_s": hist[-1]["wall_s"] / len(hist),
                   "val_curve": [h["val_acc"] for h in hist]}
            print(json.dumps(row), flush=True)
            rows.append(row)
            (OUT / "phase1_grid_partial.json").write_text(json.dumps(rows, indent=2))
    best = max(rows, key=lambda r: r["val_acc"])
    (OUT / "phase1_grid.json").write_text(json.dumps(
        {"rows": rows, "best": best, "total_wall_s": time.time() - t_start}, indent=2))
    print("\nBEST:", json.dumps(best), flush=True)
