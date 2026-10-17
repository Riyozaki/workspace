"""Image preprocessing is deterministic, train/test pixels are disjoint."""
import json
import os
from pathlib import Path
import subprocess
import sys
import numpy as np
from PIL import Image
from tensor_gp.external_data import image_dataset
from tensor_gp.experiments import ROOT


def test_image_sampling_disjoint_and_repeatable(tmp_path):
    source = (np.arange(48*64).reshape(48, 64) % 256).astype(np.uint8)
    image = tmp_path / "fixture.png"
    Image.fromarray(source).save(image)
    a = image_dataset(image, 1, (12, 8), 31)
    b = image_dataset(image, 1, (12, 8), 31)
    for x, y in zip(a[0] + list(a[1:5]), b[0] + list(b[1:5]), strict=True):
        np.testing.assert_array_equal(x, y)
    assert a[-1]["test_train_overlap_count"] == 0
    grid = np.stack(np.meshgrid(*a[0], indexing="ij"), axis=-1).reshape(-1, 2)
    assert not np.any(np.all(grid[:, None] == a[2][None, :], axis=-1))


def test_complete_real_image_workers_agree(tmp_path):
    source = np.random.default_rng(0).integers(0, 256, size=(48, 64), dtype=np.uint8)
    image = tmp_path / "fixture.png"
    Image.fromarray(source).save(image)
    predictions=[]
    for method in ("image_dense", "image_spectral"):
        stem = tmp_path / method
        proc = subprocess.run([sys.executable, "-m", "tensor_gp.run_external", "--method", method,
                              "--input", str(image), "--output", str(stem), "--axes", "12", "8",
                              "--test-size", "31", "--threads", "1"], cwd=ROOT,
                              env={**os.environ, "OPENBLAS_NUM_THREADS":"1", "OMP_NUM_THREADS":"1"},
                              capture_output=True, text=True, timeout=30)
        assert proc.returncode == 0, proc.stderr
        meta = json.loads(Path(str(stem)+".json").read_text())
        assert meta["test_train_overlap_count"] == 0
        if method == "image_spectral":
            assert not meta["scipy_loaded"]
        with np.load(Path(str(stem)+".npz")) as d:
            predictions.append((d["mean"], d["variance"]))
    for b, f in zip(*predictions, strict=True):
        np.testing.assert_allclose(b, f, atol=1e-9, rtol=1e-8)
