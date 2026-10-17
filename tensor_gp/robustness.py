"""Numerical-conditioning stress test; retain all failures and degraded quality."""
from __future__ import annotations
import argparse
import json
import random
import time
from .benchmark import compare_pair,read_protocol,write_csv
from .data import make_dataset
from .experiments import ROOT,RESULTS,log_event,run_isolated


def run(label="numerical_robustness",respect_budget=False):
    RESULTS.mkdir(parents=True,exist_ok=True)
    spec=json.loads((ROOT/"research/robustness_protocol.json").read_text())
    protocol=read_protocol()
    plan=[{"noise":noise,"ell":ell,"seed":seed} for noise in spec["model_noise_variances"]
          for ell in spec["lengthscale_pairs"] for seed in spec["seeds"]]
    random.Random(spec["randomized_plan_seed"]).shuffle(plan)
    plan_path=RESULTS/f"{label}_plan.json"
    if plan_path.exists(): raise FileExistsError(plan_path)
    plan_path.write_text(json.dumps(plan,indent=2)+"\n")
    start=json.loads((ROOT/"research/start_time.json").read_text())["start_unix"]
    rows=[]
    for i,case in enumerate(plan):
        if respect_budget and time.time()-start>spec["research_cutoff_minute"]*60:
            (RESULTS/f"{label}_unfinished.json").write_text(json.dumps(plan[i:],indent=2)+"\n")
            break
        noise,ell,seed=case["noise"],case["ell"],case["seed"]
        fixture=ROOT/f"artifacts/studies/{label}_s{seed}.npz"
        make_dataset(fixture,spec["axes"],spec["test_size"],seed)
        order=["dense_fortran","spectral_numpy"]
        if i%2: order.reverse()
        pair={}
        for method in order:
            pair[method]=run_isolated(method,fixture,
                f"{label}/case{i}_s{seed}_{method}",case=label,seed=seed,
                extra_args=["--noise-variance",noise,"--lengthscales",*ell],
                timeout=spec["timeout_seconds_per_method"])
        b,f=pair["dense_fortran"],pair["spectral_numpy"]
        row={"case_index":i,"noise_variance":noise,"lengthscale_x":ell[0],"lengthscale_y":ell[1],
             "seed":seed,"baseline_status":b["status"],"method_status":f["status"],
             "baseline_cold_s":b["cold_wall_s"],"method_cold_s":f["cold_wall_s"],
             "cold_speedup_if_both_complete":None,"quality_pass":False,
             "baseline_rmse":b.get("quality",{}).get("rmse"),"method_rmse":f.get("quality",{}).get("rmse"),
             "max_abs_mean_diff":None,"max_abs_variance_diff":None,"abs_nll_diff":None,
             "status":"solver_failure"}
        if b["status"]==f["status"]=="ok":
            c=compare_pair(b,f,protocol)
            row["cold_speedup_if_both_complete"]=c["cold_speedup"]
            for key in ("quality_pass","max_abs_mean_diff","max_abs_variance_diff","abs_nll_diff"):
                row[key]=c[key]
            row["status"]="pass" if row["quality_pass"] else "quality_fail"
        rows.append(row)
        write_csv(RESULTS/f"{label}.csv",rows)
        log_event({"event":"numerical_robustness_result","label":label,**row})
        print(json.dumps(row),flush=True)
    counts={status:sum(r["status"]==status for r in rows) for status in ("pass","quality_fail","solver_failure")}
    (RESULTS/f"{label}_summary.json").write_text(json.dumps({"planned_pairs":len(plan),"completed_pairs":len(rows),"counts":counts},indent=2)+"\n")
    return rows


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--label",default="numerical_robustness");p.add_argument("--respect-research-budget",action="store_true")
    a=p.parse_args();run(a.label,a.respect_research_budget)
