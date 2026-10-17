"""End-to-end latency benchmark: raw uint8 image -> preprocessing -> forward -> argmax.

Both baseline and student use exactly the same code path. Two fully end-to-end pipelines:
  P1: per-batch explicit normalization in NumPy.
  P2: affine normalization algebraically folded into the first-layer weights, applied to BOTH
      models identically (verified numerically against P1 before timing).
"""
import os
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import csv
import json
import time
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.data import load_fashion
from src.mlp import MLP, forward, softmax

RES = ROOT / "results"
MODELS = RES / "models"


def load_model(path: Path) -> MLP:
    z = np.load(path)
    n = sum(1 for k in z.files if k.startswith("W"))
    sizes = [z[f"W{i}"].shape[0] for i in range(n)] + [z[f"W{n-1}"].shape[1]]
    m = MLP(sizes, dropout=0.0)
    m.W = [z[f"W{i}"].copy() for i in range(n)]
    m.b = [z[f"b{i}"].copy() for i in range(n)]
    return m


def fold_norm(model: MLP, mean: float, std: float) -> MLP:
    """x = (u/255 - m)/s = u*a + c  =>  z1 = u@(a*W1) + (b1 + c*colsum(W1))."""
    a = np.float32(1.0 / (255.0 * std))
    c = np.float32(-mean / std)
    out = MLP(list(model.sizes), dropout=0.0, rng=np.random.default_rng(0))
    out.W = [w.copy() for w in model.W]
    out.b = [b.copy() for b in model.b]
    colsum = out.W[0].sum(axis=0)          # must use the ORIGINAL W1
    out.W[0] = (a * out.W[0]).astype(np.float32)
    out.b[0] = (out.b[0] + c * colsum).astype(np.float32)
    return out


def normalize(u: np.ndarray, mean: float, std: float) -> np.ndarray:
    return (u.astype(np.float32) / np.float32(255.0) - np.float32(mean)) / np.float32(std)


def pipe_p1(model, u, mean, std):
    x = normalize(u, mean, std)
    z, _ = forward(model, x, training=False)
    return z.argmax(axis=1)


def pipe_p2(model_folded, u, mean=None, std=None):
    x = u.astype(np.float32)
    z, _ = forward(model_folded, x, training=False)
    return z.argmax(axis=1)


def time_full(fn, n_items, batch, n_passes, warmup=3):
    """Time whole passes over n_items, returns list of seconds per pass."""
    n_batches = int(np.ceil(n_items / batch))
    for _ in range(warmup):
        for b in range(n_batches):
            fn(batch, b)
    times = []
    for _ in range(n_passes):
        t0 = time.perf_counter()
        for b in range(n_batches):
            fn(batch, b)
        times.append(time.perf_counter() - t0)
    return np.array(times)


def main() -> None:
    d = load_fashion()
    mean, std = float(d["mean"]), float(d["std"])
    x_test_raw = d["x_test_raw"]
    x_test_norm = d["x_test"]
    y_test = d["y_test"]
    sel = json.loads((RES / "selection.json").read_text())
    chosen = sel["chosen_width"]

    # models to benchmark: teacher + selected students (all seeds) + controls at chosen width
    metas = []
    for p in sorted(MODELS.glob("*.json")):
        m = json.loads(p.read_text())
        if m["kind"] == "baseline" or (m["kind"] == "method" and m["width"] == chosen):
            metas.append((p.with_suffix(".npz"), m))
    print(f"benchmarking {len(metas)} models; chosen width {chosen}", flush=True)

    rows = []
    for batch in (1, 256, 1024):
        n_items = 2000 if batch == 1 else 10000
        n_passes = 20 if batch == 1 else 30
        for path, meta in metas:
            model = load_model(path)
            folded = fold_norm(model, mean, std)
            # correctness check of folded pipeline vs explicit normalization
            u0 = x_test_raw[:1024]
            p1 = pipe_p1(model, u0, mean, std)
            p2 = pipe_p2(folded, u0)
            agree = float((p1 == p2).mean())
            z1, _ = forward(model, normalize(u0, mean, std))
            z2, _ = forward(folded, u0.astype(np.float32))
            maxdiff = float(np.abs(z1 - z2).max())
            if agree < 1.0:
                raise RuntimeError(f"folded pipeline mismatch for {meta['name']}: {agree}")

            buf = x_test_raw[:n_items]
            def f1(b, bi, m=model):
                s = slice(bi * b, min((bi + 1) * b, n_items))
                return pipe_p1(m, buf[s], mean, std)
            def f2(b, bi, m=folded):
                s = slice(bi * b, min((bi + 1) * b, n_items))
                return pipe_p2(m, buf[s])
            # component timings (normalization only, forward only) at this batch
            xb_norm = x_test_norm[:batch]
            xb_raw = x_test_raw[:batch]
            t_pre = []
            for _ in range(200 if batch == 1 else 30):
                t0 = time.perf_counter(); normalize(xb_raw, mean, std); t_pre.append(time.perf_counter() - t0)
            t_fwd = []
            for _ in range(200 if batch == 1 else 30):
                t0 = time.perf_counter(); forward(model, xb_norm, training=False); t_fwd.append(time.perf_counter() - t0)

            t1 = time_full(f1, n_items, batch, n_passes)
            t2 = time_full(f2, n_items, batch, n_passes)
            # correctness over the full benchmarked set (once)
            rows.append({
                "seed": meta["seed"], "name": meta["name"], "kind": meta["kind"],
                "width": meta["width"], "batch": batch, "n_items": n_items,
                "p1_ms_per_item": 1e3 * np.median(t1) / n_items,
                "p2_ms_per_item": 1e3 * np.median(t2) / n_items,
                "p2_iqr_ms": 1e3 * (np.percentile(t2, 75) - np.percentile(t2, 25)) / n_items,
                "pre_ms": 1e3 * np.median(t_pre), "fwd_ms": 1e3 * np.median(t_fwd),
                "fold_maxabs_logit_diff": maxdiff, "fold_argmax_agreement": agree,
                "flops": meta.get("flops"),
            })
            print(f"batch={batch:4d} {meta['name']:32s} P1={rows[-1]['p1_ms_per_item']:.4f} "
                  f"P2={rows[-1]['p2_ms_per_item']:.4f} ms/item  pre={rows[-1]['pre_ms']:.3f} "
                  f"fwd={rows[-1]['fwd_ms']:.3f} ms", flush=True)
    out = RES / "timings.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print("wrote", out)


if __name__ == "__main__":
    main()
