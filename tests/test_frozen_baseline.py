"""A strengthened audit must never silently rewrite the original baseline."""
import hashlib
import json
from tensor_gp.experiments import ROOT


def test_frozen_numerical_baseline_files_unchanged():
    manifest=json.loads((ROOT/'research/baseline_source_sha256.json').read_text())
    for name,expected in manifest.items():
        if name=='tensor_gp/run_one.py':
            # Dispatcher/artifact-path bug fix is documented; numerical baseline
            # and common data/kernel/metrics code must remain byte-for-byte fixed.
            continue
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,name
