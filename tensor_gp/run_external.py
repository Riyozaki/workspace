"""Strict image-to-output cold process: PNG decoding and sampling included."""
from __future__ import annotations
from time import perf_counter
MODULE_START = perf_counter()
import argparse
import json
import os
from pathlib import Path
import resource
import sys
import numpy as np
from threadpoolctl import threadpool_info, threadpool_limits
from .external_data import image_dataset
from .metrics import quality_metrics


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--method", choices=["image_dense", "image_spectral"], required=True)
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--threads", type=int, default=2)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--repeat", type=int, default=0)
    p.add_argument("--case", default="external_set12")
    p.add_argument("--axes", type=int, nargs=2, default=[128, 64])
    p.add_argument("--test-size", type=int, default=512)
    a = p.parse_args()
    output = Path(a.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with threadpool_limits(limits=a.threads):
        start = perf_counter()
        t = perf_counter()
        axes, train_y, test_x, test_y, test_latent, image_meta = image_dataset(a.input, a.seed, a.axes, a.test_size)
        stages = {"decode_and_dataset_s": perf_counter() - t}
        t = perf_counter()
        offset = float(train_y.mean())
        centered_y = train_y - offset
        stages["preprocess_s"] = perf_counter() - t
        t = perf_counter()
        if a.method == "image_dense":
            from .dense_fortran import DenseFortranGP
            model = DenseFortranGP()
        else:
            from .spectral_numpy import NumpySpectralGP
            model = NumpySpectralGP()
        stages["model_init_and_import_s"] = perf_counter() - t
        # New libraries may have loaded since the outer threadpool context.
        with threadpool_limits(limits=a.threads):
            t = perf_counter()
            model.fit(axes, centered_y)
            stages["fit_total_s"] = perf_counter() - t
            t = perf_counter()
            mean, variance = model.predict(test_x)
            mean += offset
            stages["predict_total_s"] = perf_counter() - t
        t = perf_counter()
        quality = quality_metrics(mean, variance, test_y, test_latent, 0.0025)
        stages["metrics_s"] = perf_counter() - t
        t = perf_counter()
        np.savez(Path(str(output) + ".npz"), mean=mean, variance=variance)
        stages["prediction_output_s"] = perf_counter() - t
        record = {
            "method": a.method, "case": a.case, "seed": a.seed, "repeat": a.repeat,
            "threads": a.threads, "n_train": len(train_y), "n_test": len(test_y),
            "axes": a.axes, "noise_variance": 0.0025, "lengthscales": [0.18, 0.23],
            **image_meta, "quality": quality, "stages": {**stages, **model.timings},
            "model_state_bytes": int(model.state_bytes), "min_raw_variance": model.min_raw_variance,
            "peak_rss_bytes": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024),
            "versions": {"numpy": np.__version__}, "scipy_loaded": "scipy" in sys.modules,
            "threadpools": threadpool_info(), "affinity": sorted(os.sched_getaffinity(0)),
            "pipeline_s": perf_counter() - start, "worker_s": perf_counter() - MODULE_START,
        }
        Path(str(output) + ".json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"output": str(output), "rmse": quality["rmse"],
                      "pipeline_s": record["pipeline_s"]}), flush=True)


if __name__ == "__main__":
    main()
