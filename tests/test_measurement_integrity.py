"""Regression tests for an actual invalidated extension measurement bug."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pytest
from tensor_gp.benchmark import compare_pair, read_protocol
from tensor_gp.experiments import ROOT


def test_decimal_run_id_artifacts_do_not_collide():
    a = Path("some/full_missing0.01_s0_masked_dense")
    b = Path("some/full_missing0.01_s0_masked_pcg")
    # Demonstrate and retain the precise failure mechanism.
    assert a.with_suffix(".npz") == b.with_suffix(".npz")
    assert Path(str(a) + ".npz") != Path(str(b) + ".npz")


def test_validation_rejects_same_artifact():
    record = {"status": "ok", "prediction_file": "artifacts/shared.npz"}
    with pytest.raises(ValueError, match="same prediction artifact"):
        compare_pair(record, record, read_protocol())


def test_validation_rejects_overwritten_artifact(tmp_path):
    a, b = tmp_path / "a.npz", tmp_path / "b.npz"
    np.savez(a, mean=[1.0], variance=[0.1])
    np.savez(b, mean=[1.0], variance=[0.1])
    base = {"status": "ok", "prediction_file": str(a),
            "prediction_sha256": hashlib.sha256(a.read_bytes()).hexdigest()}
    fast = {"status": "ok", "prediction_file": str(b)}
    np.savez(a, mean=[42.0], variance=[0.1])
    with pytest.raises(ValueError, match="overwritten"):
        compare_pair(base, fast, read_protocol())


def test_published_primary_artifacts_are_distinct():
    files = sorted((ROOT / "results/runs/preregistered_primary").glob("*.json"))
    if not files:
        pytest.skip("No original measurement artifacts in this checkout")
    records = [json.loads(p.read_text()) for p in files]
    paths = [r["prediction_file"] for r in records]
    assert len(paths) == len(set(paths)) == 30
    assert all("." not in Path(r["run_id"]).name for r in records)
