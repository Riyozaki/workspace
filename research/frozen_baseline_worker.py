"""One isolated cold-process end-to-end run, including input and output I/O."""
from __future__ import annotations

from time import perf_counter
MODULE_START = perf_counter()

import argparse
import json
import os
from pathlib import Path
import resource

import numpy as np
import scipy
from threadpoolctl import threadpool_info, threadpool_limits

from .data import load_dataset
from .dense import DenseGP
from .metrics import quality_metrics


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--method", choices=["dense"], required=True)
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--threads", type=int, default=2)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--repeat", type=int, default=0)
    p.add_argument("--case", default="primary")
    p.add_argument("--noise-variance", type=float, default=0.0025)
    p.add_argument("--lengthscales", type=float, nargs=2, default=[0.18, 0.23])
    a = p.parse_args()
    output = Path(a.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with threadpool_limits(limits=a.threads):
        start = perf_counter()
        t = perf_counter()
        axes, train_y, test_x, test_y, test_latent = load_dataset(a.input)
        stages = {"load_s": perf_counter() - t}
        t = perf_counter()
        offset = float(train_y.mean())
        centered_y = train_y - offset
        stages["preprocess_s"] = perf_counter() - t
        model = DenseGP(lengthscales=a.lengthscales, noise_variance=a.noise_variance)
        t = perf_counter()
        model.fit(axes, centered_y)
        stages["fit_total_s"] = perf_counter() - t
        t = perf_counter()
        mean, variance = model.predict(test_x)
        mean += offset
        stages["predict_total_s"] = perf_counter() - t
        t = perf_counter()
        quality = quality_metrics(mean, variance, test_y, test_latent, a.noise_variance)
        stages["metrics_s"] = perf_counter() - t
        t = perf_counter()
        np.savez(output.with_suffix(".npz"), mean=mean, variance=variance)
        stages["prediction_output_s"] = perf_counter() - t
        record = {
            "method": a.method, "case": a.case, "seed": a.seed, "repeat": a.repeat,
            "threads": a.threads, "n_train": int(train_y.size), "n_test": int(test_y.size),
            "axes": [len(x) for x in axes], "lengthscales": a.lengthscales,
            "noise_variance": a.noise_variance, "quality": quality,
            "stages": {**stages, **model.timings},
            "model_state_bytes": model.state_bytes,
            "min_raw_variance": model.min_raw_variance,
            "peak_rss_bytes": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024),
            "versions": {"numpy": np.__version__, "scipy": scipy.__version__},
            "threadpools": threadpool_info(),
            "affinity": sorted(os.sched_getaffinity(0)),
            "pipeline_s": perf_counter() - start,
            "worker_s": perf_counter() - MODULE_START,
        }
        output.with_suffix(".json").write_text(json.dumps(record, indent=2) + "\n")
        # Parent cold wall includes this last JSON output too. Internal timers
        # deliberately stop before their own metadata serialization.
    print(json.dumps({"output": str(output), "rmse": quality["rmse"],
                      "pipeline_s": record["pipeline_s"]}), flush=True)


if __name__ == "__main__":
    main()
