"""Pinned external image corpus and disjoint-pixel spatial-regression inputs."""
from __future__ import annotations
import base64
import hashlib
import json
from pathlib import Path
import urllib.request
import numpy as np
from .experiments import ROOT


def download_corpus():
    manifest = json.loads((ROOT / "research/external_corpus_manifest.json").read_text())
    folder = ROOT / "artifacts/corpora/set12"
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for item in manifest["files"]:
        path = folder / item["name"]
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            request = urllib.request.Request(item["api_url"], headers={"User-Agent": "reproducible-gp-study"})
            with urllib.request.urlopen(request, timeout=60) as response:
                obj = json.load(response)
            content = base64.b64decode(obj["content"])
            if hashlib.sha256(content).hexdigest() != item["sha256"]:
                raise ValueError(f"Pinned corpus hash mismatch: {path.name}")
            path.write_bytes(content)
        paths.append(path)
    return paths


def image_dataset(path, seed, shape=(128, 64), test_size=512, noise_std=0.05):
    # Image decoding AND all sampling/noise creation are charged by run_external.
    from PIL import Image
    path = Path(path)
    with Image.open(path) as image:
        pixels = np.asarray(image.convert("L"), dtype=np.float64) / 255.0
    height, width = pixels.shape
    if height < shape[0] or width < shape[1]:
        raise ValueError("Corpus image too small for the preregistered grid; do not silently resize")
    rows = np.rint(np.linspace(0, height - 1, shape[0])).astype(np.int64)
    cols = np.rint(np.linspace(0, width - 1, shape[1])).astype(np.int64)
    assert len(np.unique(rows)) == shape[0] and len(np.unique(cols)) == shape[1]
    indices = (rows[:, None] * width + cols[None, :]).ravel()
    train_y = pixels.ravel()[indices] + noise_std * np.random.default_rng(seed).standard_normal(len(indices))
    available = np.ones(height * width, dtype=bool)
    available[indices] = False
    candidates = np.flatnonzero(available)
    if len(candidates) < test_size:
        raise ValueError("Insufficient disjoint held-out pixels")
    test_rng = np.random.default_rng(10000 + seed)
    test_indices = test_rng.choice(candidates, size=test_size, replace=False)
    assert not np.any(np.isin(test_indices, indices))
    test_rows, test_cols = np.unravel_index(test_indices, (height, width))
    test_x = np.column_stack((test_rows / (height - 1), test_cols / (width - 1)))
    test_latent = pixels.ravel()[test_indices]
    test_y = test_latent + noise_std * test_rng.standard_normal(test_size)
    axes = [rows / (height - 1), cols / (width - 1)]
    metadata = {"image": path.name, "image_shape": [height, width],
                "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "train_pixel_indices_sha256": hashlib.sha256(indices.tobytes()).hexdigest(),
                "test_pixel_indices_sha256": hashlib.sha256(test_indices.tobytes()).hexdigest(),
                "test_train_overlap_count": 0}
    return axes, train_y, test_x, test_y, test_latent, metadata
