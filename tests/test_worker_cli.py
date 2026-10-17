"""End-to-end CLI smoke tests, including the exact real-world filename bug."""
import json
import os
from pathlib import Path
import subprocess
import sys
import numpy as np
import pytest
from tensor_gp.data import make_dataset
from tensor_gp.experiments import ROOT


@pytest.mark.parametrize("method", ["dense", "dense_fortran", "spectral", "spectral_numpy", "masked_dense", "masked_pcg"])
def test_real_worker_decimal_artifact_stem(tmp_path, method):
    dataset = tmp_path / "data.npz"
    make_dataset(dataset, (4, 5), 7, 2)
    stem = tmp_path / ("missing0.1_" + method)
    if method.startswith("masked"):
        module, extra = "tensor_gp.run_masked", ["--missing-fraction", "0.1"]
    elif method == "spectral_numpy":
        module, extra = "tensor_gp.run_numpy", []
    else:
        module, extra = "tensor_gp.run_one", []
    env = {**os.environ, "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}
    proc = subprocess.run([sys.executable, "-m", module, "--method", method,
                           "--input", str(dataset), "--output", str(stem), "--threads", "1", *extra],
                          cwd=ROOT, env=env, text=True, capture_output=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    metadata = json.loads(Path(str(stem) + ".json").read_text())
    assert metadata["method"] == method
    with np.load(Path(str(stem) + ".npz"), allow_pickle=False) as p:
        assert p["mean"].shape == p["variance"].shape == (7,)
        assert np.isfinite(p["mean"]).all()
    if method == "spectral_numpy":
        assert not metadata["scipy_loaded"]
