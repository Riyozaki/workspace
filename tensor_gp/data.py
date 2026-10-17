"""Independent, deterministic synthetic train/test fixtures; no test tuning."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


def latent(x):
    a, b = x[:, 0], x[:, 1]
    return (np.sin(2 * np.pi * a) * np.cos(2 * np.pi * b)
            + 0.4 * np.sin(5 * np.pi * (a + b))
            + 0.25 * np.exp(-((a - 0.68)**2 + (b - 0.31)**2) / (2 * 0.08**2)))


def make_dataset(path, axis_sizes=(128, 64), test_size=512, seed=0, noise_std=0.05):
    if len(axis_sizes) != 2:
        raise ValueError("The preregistered target function is two dimensional.")
    axes = [np.linspace(0.0, 1.0, n, dtype=np.float64) for n in axis_sizes]
    train_x = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 2)
    rng = np.random.default_rng(seed)
    train_y = latent(train_x) + noise_std * rng.standard_normal(train_x.shape[0])
    # A disjoint stream chooses continuous off-grid test inputs and their noise.
    test_rng = np.random.default_rng(10000 + seed)
    test_x = test_rng.uniform(0.0, 1.0, size=(test_size, 2))
    test_latent = latent(test_x)
    test_y = test_latent + noise_std * test_rng.standard_normal(test_size)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, axis_0=axes[0], axis_1=axes[1], train_y=train_y,
             test_x=test_x, test_y=test_y, test_latent=test_latent)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "axis_sizes": list(axis_sizes), "train_size": int(train_y.size),
            "test_size": test_size, "seed": seed, "noise_std": noise_std}


def load_dataset(path):
    with np.load(path, allow_pickle=False) as d:
        return ([d["axis_0"], d["axis_1"]], d["train_y"], d["test_x"],
                d["test_y"], d["test_latent"])


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="artifacts/datasets")
    p.add_argument("--axes", nargs=2, type=int, default=[128, 64])
    p.add_argument("--test-size", type=int, default=512)
    p.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2, 3, 4])
    a = p.parse_args()
    records = [make_dataset(Path(a.output) / f"seed_{s}.npz", a.axes, a.test_size, s) for s in a.seeds]
    manifest = Path(a.output) / "manifest.json"
    manifest.write_text(json.dumps(records, indent=2) + "\n")
    print(manifest)
