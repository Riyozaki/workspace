"""Recheck published evidence without selecting favorable runs."""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from .benchmark import compare_pair, read_protocol, summarize
from .experiments import ROOT


def verify(export_predictions=True):
    protocol=read_protocol()
    checks=[]
    frozen=json.loads((ROOT/"research/baseline_source_sha256.json").read_text())
    for p,expected in frozen.items():
        if p!="tensor_gp/run_one.py":
            assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==expected,p
    checks.append("Original dense/kernel/data/metrics numerical source hashes match pre-baseline freeze")
    rows=list(csv.DictReader((ROOT/"results.csv").open()))
    assert len(rows)==15
    assert {(int(r['seed']),int(r['repeat'])) for r in rows}=={(s,r) for s in range(5) for r in range(3)}
    recomputed=[]; proof=[]
    for row in rows:
        base=json.loads((ROOT/"results/runs"/(row['baseline_run_id']+'.json')).read_text())
        fast=json.loads((ROOT/"results/runs"/(row['method_run_id']+'.json')).read_text())
        check=compare_pair(base,fast,protocol)
        assert check['quality_pass']
        for k in ('baseline_cold_s','method_cold_s','max_abs_mean_diff','max_abs_variance_diff'):
            assert abs(float(row[k])-check[k])<1e-12,(k,row)
        recomputed.append(check)
        if export_predictions and int(row['repeat'])==0:
            seed=int(row['seed'])
            with np.load(ROOT/f'artifacts/datasets/seed_{seed}.npz') as d, \
                 np.load(ROOT/base['prediction_file']) as b, np.load(ROOT/fast['prediction_file']) as f:
                assert abs(float(np.sqrt(np.mean((b['mean']-d['test_y'])**2)))-base['quality']['rmse'])<1e-15
                assert abs(float(np.sqrt(np.mean((f['mean']-d['test_y'])**2)))-fast['quality']['rmse'])<1e-15
                for i in range(len(d['test_y'])):
                    proof.append({'seed':seed,'index':i,'test_x':float(d['test_x'][i,0]),'test_y_coordinate':float(d['test_x'][i,1]),
                        'heldout_target':float(d['test_y'][i]),'baseline_mean':float(b['mean'][i]),'method_mean':float(f['mean'][i]),
                        'baseline_latent_variance':float(b['variance'][i]),'method_latent_variance':float(f['variance'][i])})
    summary=summarize(recomputed)
    original=json.loads((ROOT/'results/preregistered_primary_summary.json').read_text())
    assert abs(summary['primary_speedup_ratio_of_sums']-original['primary_speedup_ratio_of_sums'])<1e-12
    np.testing.assert_allclose(summary['primary_speedup_cluster_bootstrap_95ci'],original['primary_speedup_cluster_bootstrap_95ci'],rtol=0,atol=1e-12)
    checks.append('All 15 primary pairs, all quality guards, raw wall times and clustered bootstrap independently recomputed')
    seal=json.loads((ROOT/'research/primary_prediction_sha256.json').read_text())
    for path,expected in seal.items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==expected,path
    checks.append('All 30 original primary prediction SHA-256 seals still match')
    records=[json.loads(p.read_text()) for p in (ROOT/'results/runs').rglob('*.json')]
    counts=Counter();hashes=0;pools=0;invalid=0
    for record in records:
        counts[record.get('status','unknown')]+=1
        if record.get('measurement_valid') is False:
            invalid+=1;continue
        if record.get('status')!='ok': continue
        if 'prediction_sha256' in record:
            assert hashlib.sha256((ROOT/record['prediction_file']).read_bytes()).hexdigest()==record['prediction_sha256'],record['run_id']
            hashes+=1
        for pool in record.get('threadpools',[]):
            assert pool['num_threads']==record['threads'],(record['run_id'],pool)
            pools+=1
        if 'test_train_overlap_count' in record:
            assert record['test_train_overlap_count']==0
    checks.append(f'Validated {hashes} non-invalidated artifact hashes and {pools} recorded library thread limits; {invalid} historical invalidated runs retained')
    if proof:
        out=ROOT/'results/primary_predictions.csv'
        with out.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(proof[0]));w.writeheader();w.writerows(proof)
    report={'checks':checks,'raw_run_status_counts':dict(counts),'invalidated_historical_runs':invalid,
            'verified_prediction_hashes':hashes,'verified_threadpool_records':pools,
            'primary_pairs':15,'primary_summary_recomputed':summary,'all_checks_pass':True}
    (ROOT/'results/integrity_audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2));return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--no-export',action='store_true');a=p.parse_args();verify(not a.no_export)
