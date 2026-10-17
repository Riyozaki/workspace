"""Independent input/source/prediction/paired-timing audit; no evaluator edits."""
from __future__ import annotations
import csv,hashlib,json
from datetime import datetime
from pathlib import Path
import numpy as np
from .data import ROOT,ART,DATA,images,labels,digest
from .eval import evaluate
from .primary import verify_method


def main():
 frozen=verify_method();manifest=json.loads((ROOT/'data_manifest.json').read_text())
 assert manifest['commit']==json.loads((ROOT/'source_commit.json').read_text())['commit']
 for r in manifest['files']:
  raw=(DATA/r['name']).read_bytes();assert hashlib.sha256(raw).hexdigest()==r['sha256'];assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==r['git_blob_sha1']
 from sklearn.model_selection import train_test_split
 y_all=labels(DATA/'t10k-labels-idx1-ubyte.gz');v,h=train_test_split(np.arange(10000),test_size=.5,stratify=y_all,random_state=20261017)
 with np.load(ART/'splits.npz',allow_pickle=False) as z:
  np.testing.assert_array_equal(v,z['validation']);np.testing.assert_array_equal(h,z['holdout'])
 assert not set(v)&set(h);assert len(v)==len(h)==5000
 rows=list(csv.DictReader((ROOT/'results.csv').open()));assert len(rows)==5
 computed=[];prediction_count=0;failures=[]
 for p in (ROOT/'results/runs').glob('*.json'):
  r=json.loads(p.read_text())
  if r['status']!='ok':failures.append({'run_id':r['run_id'],'status':r['status']});continue
  assert digest(ROOT.parent/r['prediction_path'])==r['prediction_sha256'];prediction_count+=1
 for row in rows:
  b=json.loads((ROOT/'results/runs'/f'{row["baseline_run_id"]}.json').read_text());m=json.loads((ROOT/'results/runs'/f'{row["method_run_id"]}.json').read_text())
  assert b['prediction_path']!=m['prediction_path']
  for r in (b,m):
   for name,sha in frozen['source_and_model_sha256'].items():
    if '/' not in name and name.endswith('.py'):assert r['source_sha256'][name]==sha
  bp=np.load(ROOT.parent/b['prediction_path'],allow_pickle=False);mp=np.load(ROOT.parent/m['prediction_path'],allow_pickle=False)
  metric=evaluate(y_all[h],bp,mp);assert metric['quality_pass']
  assert abs(metric['baseline_accuracy']-float(row['baseline_accuracy']))<1e-15
  assert abs(metric['candidate_accuracy']-float(row['candidate_accuracy']))<1e-15
  extra=float(row['quality_comparison_seconds']);assert extra>=0
  assert abs(b['cold_seconds']+extra-float(row['baseline_endpoint_seconds']))<1e-10
  assert abs(m['cold_seconds']+extra-float(row['method_endpoint_seconds']))<1e-10
  computed.append((float(row['baseline_endpoint_seconds']),float(row['method_endpoint_seconds'])))
 a=np.array(computed);ratio=float(a[:,0].sum()/a[:,1].sum());rng=np.random.default_rng(20261017);ix=rng.integers(0,5,(10000,5));ci=np.quantile(a[ix,0].sum(1)/a[ix,1].sum(1),[.025,.975]).tolist()
 s=json.loads((ROOT/'results/primary_summary.json').read_text());assert abs(ratio-s['speedup_ratio_of_sums'])<1e-12;np.testing.assert_allclose(ci,s['paired_bootstrap_95ci'],rtol=0,atol=1e-12)
 events=[json.loads(line) for line in (ROOT/'results/experiments.jsonl').read_text().splitlines()]
 starts=[e['wall_unix'] for e in events if e['event']=='run_start' and e.get('split')=='holdout']
 assert min(starts)>=datetime.fromisoformat(frozen['utc']).timestamp()
 # Content duplicate audit is post-freeze, never used to select/remove data.
 train=images(DATA/'train-images-idx3-ubyte.gz');test=images(DATA/'t10k-images-idx3-ubyte.gz')
 hashes={hashlib.sha256(row).digest() for row in train};test_hashes=[hashlib.sha256(row).digest() for row in test]
 duplicates={'official_train_unique_images':len(hashes),'official_test_exact_matches_train':sum(t in hashes for t in test_hashes),'validation_exact_matches_train':sum(test_hashes[i] in hashes for i in v),'holdout_exact_matches_train':sum(test_hashes[i] in hashes for i in h),'validation_holdout_content_overlap_unique':len({test_hashes[i] for i in v}&{test_hashes[i] for i in h})}
 r={'all_checks_pass':True,'frozen_protocol_and_evaluator_unchanged':True,'fixed_seed_splits_independently_recomputed':True,'all_four_raw_dataset_sha256_and_git_blob_sha1_verified':True,'primary_pairs_independently_recomputed':5,'speedup_recomputed':ratio,'bootstrap_ci_recomputed':ci,'verified_prediction_artifacts':prediction_count,'failed_worker_attempts_retained':failures,'first_holdout_after_method_freeze':True,'content_duplicate_audit':duplicates,'scope':'local reproducibility/integrity, not external organizer verification'}
 (ROOT/'results/integrity_audit.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()
