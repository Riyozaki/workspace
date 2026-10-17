"""Predeclared late-time unseen-seed audit, then useful residual checks to deadline."""
from __future__ import annotations
import json
import time
import numpy as np
from .benchmark import compare_pair,read_protocol,summarize,write_csv
from .data import make_dataset
from .experiments import ROOT,RESULTS,log_event,run_isolated
from .kernels import kernel_factors
from .spectral_numpy import NumpySpectralGP


def main():
    protocol=read_protocol()
    start=json.loads((ROOT/'research/start_time.json').read_text())
    def elapsed(): return min(time.time()-start['start_unix'],time.monotonic()-start['start_monotonic'])
    label='late_stability'
    plan=list(range(100,400))
    path=RESULTS/f'{label}_plan.json'
    if path.exists(): raise FileExistsError(path)
    path.write_text(json.dumps({'seeds':plan,'full_pair_cutoff_seconds':5360,'deadline_seconds':5400},indent=2)+'\n')
    rows=[];failures=[];attempted=[]
    for seed in plan:
        if elapsed()>=5360: break
        attempted.append(seed)
        fixture=ROOT/f'artifacts/studies/{label}_s{seed}.npz'
        make_dataset(fixture,(128,64),512,seed)
        methods=['dense_fortran','spectral_numpy']
        if seed%2: methods.reverse()
        pair={}
        for method in methods:
            pair[method]=run_isolated(method,fixture,f'{label}/s{seed}_{method}',case=label,seed=seed,timeout=30)
        if any(r['status']!='ok' for r in pair.values()):
            failures.append({'seed':seed,'statuses':{k:v['status'] for k,v in pair.items()}})
            (RESULTS/f'{label}_failed_pairs.json').write_text(json.dumps(failures,indent=2)+'\n')
            continue
        row=compare_pair(pair['dense_fortran'],pair['spectral_numpy'],protocol)
        rows.append(row);write_csv(RESULTS/f'{label}.csv',rows)
        log_event({'event':'late_pair_validation',**row})
    if rows:
        summary=summarize(rows)
        summary.update(candidate_pairs=len(plan),attempted_pairs=len(attempted),failed_pairs=len(failures),
                       unstarted_seeds=[s for s in plan if s not in attempted],
                       cutoff_reason='predeclared time budget, not filtering by outcome',elapsed_at_full_pair_end=elapsed())
        (RESULTS/f'{label}_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    # No timed comparative ML run overlaps this numerical-residual phase.
    # These are NOT system acceleration measurements and cannot enter the ratio.
    axes=[np.linspace(0,1,128),np.linspace(0,1,64)]
    gp=NumpySpectralGP().fit(axes,np.zeros(8192))
    kx,ky=kernel_factors(axes,(.18,.23),1.0)
    rng=np.random.default_rng(987654)
    count=0;maximum=0.0;fail_count=0
    while elapsed()<5400:
        rhs=rng.standard_normal(8192)
        alpha=gp.solve(rhs).reshape(128,64)
        residual=(kx@alpha@ky.T+.0025*alpha).ravel()-rhs
        relative=float(np.linalg.norm(residual)/np.linalg.norm(rhs))
        count+=1;maximum=max(maximum,relative);fail_count+=int(relative>1e-8)
    residual_record={'probes':count,'max_relative_residual':maximum,'tolerance':1e-8,
                     'failed_probes':fail_count,'all_pass':fail_count==0,'elapsed_end_seconds':elapsed(),
                     'interpretation':'algebraic validation only; no new system speedup claimed'}
    (RESULTS/'deadline_residual_audit.json').write_text(json.dumps(residual_record,indent=2)+'\n')
    log_event({'event':'deadline_residual_audit',**residual_record})
    print(json.dumps({'late_pairs':len(rows),'residual_validation':residual_record},indent=2),flush=True)


if __name__=='__main__': main()
