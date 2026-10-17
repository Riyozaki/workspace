"""Five complete paired holdout requests after numerical code is frozen."""
from __future__ import annotations
import argparse,hashlib,json,random,time
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from .clock import snapshot
from .data import ROOT,ART,DATA,labels
from .harness import RESULTS,run,compare,write_csv,summary,status,event,sha,verify_frozen,predictions

NUMERIC_FILES=['eval.py','reference_worker.py','data.py','candidate_worker.py','request_data.py','paths.py','inference.py','u8gemm.c','artifacts/libu8gemm.so','artifacts/model_compact.npz','artifacts/model.joblib']


def freeze(block,validation_source):
 verify_frozen();path=ROOT/'method_frozen.json'
 if path.exists():raise FileExistsError(path)
 r={'utc':datetime.now(timezone.utc).isoformat(),'engine':'compact','block':int(block),'validation_source':validation_source,'precision':'exact uint8 dot and squared distance, float32 scaled exp, float64 decision FMA','source_and_model_sha256':{p:sha(ROOT/p) for p in NUMERIC_FILES},'baseline_engine':json.loads((RESULTS/'baseline_selected.json').read_text())['selected_engine'],'holdout_previously_scored':False}
 path.write_text(json.dumps(r,indent=2)+'\n');event({'event':'method_frozen_before_holdout',**r});return r


def verify_method():
 r=json.loads((ROOT/'method_frozen.json').read_text());verify_frozen()
 for p,h in r['source_and_model_sha256'].items():
  if sha(ROOT/p)!=h:raise RuntimeError('Frozen method/model changed: '+p)
 return r


def main():
 p=argparse.ArgumentParser();p.add_argument('--label',default='primary');p.add_argument('--repetitions',type=int,default=5);a=p.parse_args()
 frozen=verify_method();engine=frozen['engine'];block=frozen['block'];baseline=frozen['baseline_engine']
 snapshot('Stage 7 — frozen-candidate full holdout inference',f'{a.label}: fixed engine={engine}, block={block}, baseline={baseline}; {a.repetitions} paired fresh processes; no optimization after seeing holdout.')
 if (RESULTS/f'{a.label}_plan.json').exists():raise FileExistsError(a.label)
 plan=list(range(a.repetitions));random.Random(20261017).shuffle(plan)
 (RESULTS/f'{a.label}_plan.json').write_text(json.dumps({'pair_order':plan,'baseline_first_even_repeat':True,'repetitions':a.repetitions},indent=2)+'\n')
 rows=[];failures=[]
 for rep in plan:
  verify_method();order=[baseline,engine] if rep%2==0 else [engine,baseline];records={}
  for e in order:records[e]=run(e,'holdout',f'{a.label}_{e}_r{rep}',block)
  if any(r['status']!='ok' for r in records.values()):
   failures.append({'repeat':rep,'statuses':{e:r['status'] for e,r in records.items()}});continue
  row=compare(records[baseline],records[engine]);row.update(repeat=rep,order='baseline_first' if rep%2==0 else 'method_first')
  rows.append(row);write_csv(ROOT/'results.csv' if a.label=='primary' else RESULTS/f'{a.label}.csv',rows)
  s=summary(rows);status(stage=f'{a.label} holdout {len(rows)}/{a.repetitions} pairs',measured_speedup=s['speedup_ratio_of_sums'],quality={'baseline_accuracy':s['baseline_accuracy'],'method_accuracy':s['candidate_accuracy'],'agreement':s['min_label_agreement'],'all_gates':s['all_quality_pass']},verification_probability_percent=92 if len(rows)==a.repetitions else 85,main_risk='ONE public locally sequestered holdout; timing CI is not dataset-generalization evidence; inference-only scope and one-time preparation must remain explicit.')
  if len(rows)==1:
   with np.load(ART/'splits.npz',allow_pickle=False) as z:idx=z['holdout']
   y=labels(DATA/'t10k-labels-idx1-ubyte.gz')[idx];bp=predictions(records[baseline]);mp=predictions(records[engine])
   import csv
   with (RESULTS/f'{a.label}_predictions.csv').open('w',newline='') as f:
    w=csv.writer(f);w.writerow(['official_test_index','label','baseline_prediction','method_prediction']);w.writerows(zip(idx.tolist(),y.tolist(),bp.tolist(),mp.tolist()))
 s=summary(rows) if rows else {'n_pairs':0,'all_quality_pass':False}
 s.update(planned_pairs=a.repetitions,attempted_pairs=a.repetitions,failed_pairs=failures,complete=len(rows)==a.repetitions and not failures,baseline_engine=baseline,method_engine=engine,block=block,scope='PRIMARY local holdout only' if a.label=='primary' else 'SECONDARY reproduction; not pooled with primary')
 s['all_quality_pass']=s['all_quality_pass'] and s['complete']
 (RESULTS/f'{a.label}_summary.json').write_text(json.dumps(s,indent=2)+'\n');event({'event':a.label+'_completed',**s});print(json.dumps(s,indent=2),flush=True)
 if not s['all_quality_pass']:raise SystemExit('Primary/reproduction incomplete or frozen quality gate failed')
if __name__=='__main__':main()
