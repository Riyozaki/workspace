"""Report actual software/hardware, not vendor peak-performance assumptions."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import numpy as np
import scipy
import psutil
from threadpoolctl import threadpool_info


def capture():
    cpu = subprocess.run(["lscpu"], capture_output=True, text=True, check=False)
    return {"utc": datetime.now(timezone.utc).isoformat(), "python": sys.version,
            "executable": sys.executable, "platform": platform.platform(),
            "cpu_count": os.cpu_count(), "cpu_affinity": sorted(os.sched_getaffinity(0)),
            "memory_total_bytes": psutil.virtual_memory().total,
            "numpy": np.__version__, "scipy": scipy.__version__,
            "threadpools": threadpool_info(), "lscpu": cpu.stdout,
            "thread_environment": {k: os.environ.get(k) for k in
                ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")},
            "gpu": "No GPU used; CPU numerical libraries only",
            "isolation": "Sequential timed workers; shared virtualized host, no exclusive-core or cold-page-cache guarantee"}


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(); p.add_argument("--output", default="results/environment.json")
    a = p.parse_args(); path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(capture(), indent=2)+"\n");print(path)
