"""Main training sweep. Test set is never touched here: only validation metrics are computed.

For every seed:
  teacher (baseline, frozen config) -> soft targets -> for each student width in the
  pre-registered grid: DistillPrune (pruned init + distillation fine-tune).
  Additionally, controls at the two mid-grid widths: HardScratch, DistillScratch.
Models and validation metrics are persisted so that test evaluation can be frozen separately.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.data import load_fashion
from src.mlp import (MLP, accuracy, count_params, distillation_targets, evaluate,
                     forward_flops_per_sample, prune_teacher, train)

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"
MODELS = RES / "models"
MODELS.mkdir(parents=True, exist_ok=True)

GRID = [(96, 64), (128, 64), (160, 96), (192, 128), (224, 160)]
CONTROL_WIDTHS = [(128, 64), (192, 128)]
TEACHER_EPOCHS = 15
STUDENT_EPOCHS = 30
T = 4.0
ALPHA = 0.5


def save_model(model: MLP, name: str, meta: dict) -> None:
    payload = {f"W{i}": w for i, w in enumerate(model.W)}
    payload.update({f"b{i}": b for i, b in enumerate(model.b)})
    np.savez_compressed(MODELS / f"{name}.npz", **payload)
    (MODELS / f"{name}.json").write_text(json.dumps(meta, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--config", default=str(RES / "frozen_config.json"))
    ap.add_argument("--out", default=str(RES / "runs.jsonl"))
    ap.add_argument("--skip-controls", action="store_true",
                    help="only teacher + DistillPrune grid (used for extra seeds)")
    ap.add_argument("--time-budget", type=float, default=1200.0,
                    help="soft budget in seconds; stops starting new runs after it")
    args = ap.parse_args()
    seeds = [int(s) for s in args.seeds.split(",")]
    cfg = json.loads(Path(args.config).read_text())
    d = load_fashion()
    print("config:", cfg, flush=True)

    t_all = time.time()
    with open(args.out, "a") as fout:
        for seed in seeds:
            if time.time() - t_all > args.time_budget:
                print("soft time budget exhausted, stopping", flush=True)
                break
            print(f"\n########## seed {seed} ##########", flush=True)
            # ---------------- teacher / baseline
            rng = np.random.default_rng(seed)
            teacher = MLP([784, 1024, 1024, 10], dropout=cfg["dropout"], rng=rng)
            t0 = time.time()
            hist = train(teacher, d["x_train"], d["y_train"], epochs=TEACHER_EPOCHS,
                         lr=cfg["lr"], weight_decay=1e-4, x_val=d["x_val"], y_val=d["y_val"],
                         seed=seed)
            t_teacher = time.time() - t0
            v = evaluate(teacher, d["x_val"], d["y_val"])
            rec = {"seed": seed, "name": "teacher", "kind": "baseline", "width": "1024-1024",
                   "val_acc": v["acc"], "val_f1": v["macro_f1"], "val_ece": v["ece"],
                   "params": count_params(teacher), "flops": forward_flops_per_sample(teacher),
                   "train_wall_s": t_teacher, "epochs": TEACHER_EPOCHS,
                   "val_curve": [h["val_acc"] for h in hist]}
            print("TEACHER", json.dumps({k: rec[k] for k in ("val_acc", "train_wall_s")}), flush=True)
            save_model(teacher, f"seed{seed}_teacher", rec)
            fout.write(json.dumps(rec) + "\n"); fout.flush()

            # ---------------- soft targets (teacher forward on train set)
            t0 = time.time()
            soft = distillation_targets(teacher, d["x_train"], T)
            t_soft = time.time() - t0
            print(f"soft targets: {soft.shape} in {t_soft:.1f}s", flush=True)

            # ---------------- DistillPrune over the grid
            for (w1, w2) in GRID:
                if time.time() - t_all > args.time_budget:
                    print("budget exhausted before width", (w1, w2), flush=True)
                    break
                name = f"seed{seed}_distillprune_{w1}x{w2}"
                student = prune_teacher(teacher, w1, w2)
                t0 = time.time()
                shist = train(student, d["x_train"], d["y_train"], epochs=STUDENT_EPOCHS,
                              lr=cfg["student_lr"], weight_decay=1e-4, soft_targets=soft,
                              alpha=ALPHA, temperature=T, x_val=d["x_val"], y_val=d["y_val"],
                              seed=seed + 100)
                t_train = time.time() - t0
                v = evaluate(student, d["x_val"], d["y_val"])
                rec = {"seed": seed, "name": f"distillprune_{w1}x{w2}", "kind": "method",
                       "width": f"{w1}-{w2}", "val_acc": v["acc"], "val_f1": v["macro_f1"],
                       "val_ece": v["ece"], "params": count_params(student),
                       "flops": forward_flops_per_sample(student),
                       "flops_ratio_vs_teacher": forward_flops_per_sample(teacher) / forward_flops_per_sample(student),
                       "train_wall_s": t_train + t_teacher + t_soft, "epochs": STUDENT_EPOCHS,
                       "val_curve": [h["val_acc"] for h in shist]}
                print("  ", rec["name"], f"val={v['acc']:.4f}", f"{t_train:.1f}s", flush=True)
                save_model(student, name, rec)
                fout.write(json.dumps(rec) + "\n"); fout.flush()

            # ---------------- controls at mid-grid widths
            for (w1, w2) in ([] if args.skip_controls else CONTROL_WIDTHS):
                for kind in ("hard_scratch", "distill_scratch"):
                    if time.time() - t_all > args.time_budget:
                        print("budget exhausted before control", kind, (w1, w2), flush=True)
                        break
                    name = f"seed{seed}_{kind}_{w1}x{w2}"
                    student = MLP([784, w1, w2, 10], dropout=cfg["dropout"],
                                  rng=np.random.default_rng(seed + 555))
                    t0 = time.time()
                    shist = train(
                        student, d["x_train"], d["y_train"], epochs=STUDENT_EPOCHS,
                        lr=cfg["student_lr"], weight_decay=1e-4,
                        soft_targets=(soft if kind == "distill_scratch" else None),
                        alpha=ALPHA, temperature=T, x_val=d["x_val"], y_val=d["y_val"],
                        seed=seed + 100)
                    t_train = time.time() - t0
                    v = evaluate(student, d["x_val"], d["y_val"])
                    rec = {"seed": seed, "name": f"{kind}_{w1}x{w2}", "kind": kind,
                           "width": f"{w1}-{w2}", "val_acc": v["acc"], "val_f1": v["macro_f1"],
                           "val_ece": v["ece"], "params": count_params(student),
                           "flops": forward_flops_per_sample(student),
                           "flops_ratio_vs_teacher": forward_flops_per_sample(teacher) / forward_flops_per_sample(student),
                           "train_wall_s": t_train, "epochs": STUDENT_EPOCHS,
                           "val_curve": [h["val_acc"] for h in shist]}
                    print("  ", rec["name"], f"val={v['acc']:.4f}", f"{t_train:.1f}s", flush=True)
                    save_model(student, name, rec)
                    fout.write(json.dumps(rec) + "\n"); fout.flush()
    print(f"\nDONE in {time.time() - t_all:.1f}s", flush=True)


if __name__ == "__main__":
    main()
