"""End-to-end GP hyperparameter learning, including all line searches/refit."""
from __future__ import annotations
from time import perf_counter
MODULE_START = perf_counter()
import argparse
import json
import os
from pathlib import Path
import resource
import warnings
import numpy as np
import scipy
from threadpoolctl import threadpool_info, threadpool_limits
from .data import load_dataset
from .hyperparameters import SklearnHyperGP, TensorHyperGP
from .metrics import quality_metrics


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--method", choices=["hyper_dense", "hyper_spectral"], required=True)
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--threads", type=int, default=2)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--repeat", type=int, default=0)
    p.add_argument("--case", default="hyperparameters")
    a = p.parse_args()
    output = Path(a.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    spec = json.loads((Path(__file__).resolve().parents[1] / "research/hyperparameter_protocol.json").read_text())
    with threadpool_limits(limits=a.threads), warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        start = perf_counter()
        t = perf_counter()
        axes, train_y, test_x, test_y, test_latent = load_dataset(a.input)
        stages = {"load_s": perf_counter() - t}
        t = perf_counter()
        offset = float(train_y.mean())
        centered_y = train_y - offset
        stages["preprocess_s"] = perf_counter() - t
        model = (SklearnHyperGP(spec) if a.method == "hyper_dense" else TensorHyperGP(spec))
        t = perf_counter()
        model.fit(axes, centered_y)
        stages["fit_total_s"] = perf_counter() - t
        t = perf_counter()
        mean, variance = model.predict(test_x)
        mean += offset
        stages["predict_total_s"] = perf_counter() - t
        t = perf_counter()
        quality = quality_metrics(mean, variance, test_y, test_latent, model.noise_variance)
        stages["metrics_s"] = perf_counter() - t
        t = perf_counter()
        np.savez(Path(str(output) + ".npz"), mean=mean, variance=variance)
        stages["prediction_output_s"] = perf_counter() - t
        opt = model.optimization
        record = {
            "method": a.method, "case": a.case, "seed": a.seed, "repeat": a.repeat,
            "threads": a.threads, "n_train": int(train_y.size), "n_test": int(test_y.size),
            "axes": [len(x) for x in axes], "theta": model.theta.tolist(),
            "noise_variance": model.noise_variance, "quality": quality, "stages": stages,
            "optimizer_success": bool(opt.success), "optimizer_message": str(opt.message),
            "optimizer_iterations": int(opt.nit), "optimizer_nfev": int(opt.nfev),
            "optimizer_njev": int(opt.njev), "final_negative_lml": float(opt.fun),
            "optimizer_history": model.history,
            "warnings": [{"category": w.category.__name__, "message": str(w.message)} for w in captured],
            "model_state_bytes": int(model.state_bytes), "min_raw_variance": model.min_raw_variance,
            "peak_rss_bytes": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024),
            "versions": {"numpy": np.__version__, "scipy": scipy.__version__},
            "threadpools": threadpool_info(), "affinity": sorted(os.sched_getaffinity(0)),
            "pipeline_s": perf_counter() - start, "worker_s": perf_counter() - MODULE_START,
        }
        Path(str(output) + ".json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"output": str(output), "rmse": quality["rmse"],
                      "pipeline_s": record["pipeline_s"], "nfev": opt.nfev}), flush=True)


if __name__ == "__main__":
    main()
