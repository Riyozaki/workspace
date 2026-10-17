"""Fashion-MNIST loading and the exact train/val/test split fixed in PREREGISTRATION.md."""
from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "fashion"
VAL_SIZE = 5_000


def _read_idx_images(path: Path) -> np.ndarray:
    with gzip.open(path, "rb") as f:
        magic = int.from_bytes(f.read(4), "big")
        if magic != 2051:
            raise ValueError(f"bad magic {magic} in {path}")
        n = int.from_bytes(f.read(4), "big")
        rows = int.from_bytes(f.read(4), "big")
        cols = int.from_bytes(f.read(4), "big")
        buf = f.read(n * rows * cols)
    return np.frombuffer(buf, dtype=np.uint8).reshape(n, rows * cols).copy()


def _read_idx_labels(path: Path) -> np.ndarray:
    with gzip.open(path, "rb") as f:
        magic = int.from_bytes(f.read(4), "big")
        if magic != 2049:
            raise ValueError(f"bad magic {magic} in {path}")
        n = int.from_bytes(f.read(4), "big")
        buf = f.read(n)
    return np.frombuffer(buf, dtype=np.uint8).astype(np.int64).copy()


def load_fashion(val_size: int = VAL_SIZE) -> dict[str, np.ndarray]:
    x_all = _read_idx_images(DATA_DIR / "train-images-idx3-ubyte.gz")
    y_all = _read_idx_labels(DATA_DIR / "train-labels-idx1-ubyte.gz")
    x_test = _read_idx_images(DATA_DIR / "t10k-images-idx3-ubyte.gz")
    y_test = _read_idx_labels(DATA_DIR / "t10k-labels-idx1-ubyte.gz")

    x_tr, y_tr = x_all[:-val_size], y_all[:-val_size]
    x_val, y_val = x_all[-val_size:], y_all[-val_size:]

    mean = x_tr.astype(np.float32).mean() / 255.0
    std = x_tr.astype(np.float32).std() / 255.0

    def prep(x: np.ndarray) -> np.ndarray:
        return (x.astype(np.float32) / 255.0 - mean) / std

    return {
        "x_train": prep(x_tr), "y_train": y_tr,
        "x_val": prep(x_val), "y_val": y_val,
        "x_test": prep(x_test), "y_test": y_test,
        "x_test_raw": x_test,          # uint8, used for the end-to-end timing pipeline
        "mean": np.float32(mean), "std": np.float32(std),
    }


if __name__ == "__main__":
    d = load_fashion()
    for k, v in d.items():
        if hasattr(v, "shape"):
            print(f"{k:12s} {str(v.shape):18s} {v.dtype}")
    print("class counts train:", np.bincount(d["y_train"]))
