"""One-command reproduction; never overwrite the original published experiment."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from .experiments import ROOT


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--all", action="store_true", help="Also run scale, masked, learned-hyperparameter and all-image studies (can take ~1 hour on 2 CPUs)")
    p.add_argument("--output", default=None)
    a=p.parse_args()
    tag=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    output=Path(a.output).resolve() if a.output else ROOT/f"artifacts/reproductions/{tag}"
    output.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env["GP_RESULTS_DIR"]=str(output)
    for key in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS","VECLIB_MAXIMUM_THREADS","NUMEXPR_NUM_THREADS","BLIS_NUM_THREADS"):
        env[key]="2"
    env["PYTHONHASHSEED"]="0"
    steps=[("environment",["-m","tensor_gp.environment","--output",str(output/"environment.json")]),
           ("tests",["-m","pytest","-q","tests"]),
           ("primary",["-m","tensor_gp.benchmark","--label","primary_"+tag,"--csv",str(output/"results.csv")]),
           ("four_way",["-m","tensor_gp.audits","four-way","--label","fourway_"+tag])]
    if a.all:
        steps.extend([
            ("scaling",["-m","tensor_gp.audits","scaling","--label","scaling_"+tag]),
            ("scaling_tuned",["-m","tensor_gp.audits","scaling-tuned","--label","scaling_tuned_"+tag]),
            ("masked",["-m","tensor_gp.masked_audit","--label","masked_"+tag]),
            ("hyperparameters",["-m","tensor_gp.hyper_audit","--label","hyper_"+tag]),
            ("external_set12",["-m","tensor_gp.external_audit","--label","set12_"+tag]),
            ("numerical_robustness",["-m","tensor_gp.robustness","--label","robustness_"+tag])])
    index={"tag":tag,"output":str(output),"all":a.all,"steps":[]}
    for name,args in steps:
        print(f"\n=== {name} ===",flush=True)
        t=perf_counter()
        proc=subprocess.run([sys.executable,*args],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        (output/(name+".log")).write_text(proc.stdout)
        print(proc.stdout,flush=True)
        index["steps"].append({"name":name,"command":[sys.executable,*args],"returncode":proc.returncode,"duration_s":perf_counter()-t})
        (output/"reproduction_index.json").write_text(json.dumps(index,indent=2)+"\n")
        if proc.returncode:
            raise SystemExit(f"{name} failed: see {output/(name+'.log')}; no failed run is discarded.")
    summaries={p.name:json.loads(p.read_text()) for p in output.glob("*_summary.json")}
    (output/"all_summaries.json").write_text(json.dumps(summaries,indent=2)+"\n")
    print(f"\nReproduction complete. Original results were not overwritten.\n{output}\nPrimary pairs: {output/'results.csv'}",flush=True)


if __name__=="__main__":
    main()
