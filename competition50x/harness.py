"""Cold-process measurements, append-only attempts and byte-level provenance."""
from __future__ import annotations
import csv,hashlib,json,os,subprocess,sys,time
from pathlib import Path
import numpy as np
from .data import ROOT,ART,DATA,labels
from .eval import evaluate
REPO=ROOT.parent;RESULTS=ROOT/'results';RESULTS.mkdir(exist_ok=True)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def verify_frozen():
 seal=json.loads((ROOT/'protocol_frozen.json').read_text())
 for name,expected in seal['files'].items():
  if sha(ROOT/name)!=expected:raise RuntimeError('Frozen file modified: '+name)
 return seal['files']['eval.py']
def event(r):
 with (RESULTS/'experiments.jsonl').open('a') as f:f.write(json.dumps({'wall_unix':time.time(),**r})+'\n')
def status(**kwargs):
 p=RESULTS/'status.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(kwargs,indent=2)+'\n');tmp.replace(p)

def run(engine,split,run_id,block=512,timeout=180):
 evaluator_hash=verify_frozen();prefix=ART/'runs'/run_id;record=RESULTS/'runs'/f'{run_id}.json'
 if record.exists() or Path(str(prefix)+'.pred.npy').exists():raise FileExistsError(run_id)
 prefix.parent.mkdir(parents=True,exist_ok=True);record.parent.mkdir(parents=True,exist_ok=True)
 reference=engine in ('native','threaded','onnx')
 cmd=[sys.executable,'-m','competition50x.reference_worker' if reference else 'competition50x.candidate_worker','--engine',engine,'--split',split,'--output',str(prefix)]
 if not reference:cmd+=['--block',str(block)]
 env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2')
 r={'run_id':run_id,'engine':engine,'split':split,'block':block,'command':cmd,'eval_sha256':evaluator_hash,'source_sha256':{p.name:sha(p) for p in ROOT.glob('*.py')},'affinity':sorted(os.sched_getaffinity(0))}
 r['native_artifact_sha256']={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'u8gemm.c',ART/'libu8gemm.so',ART/'model_compact.npz') if p.exists()}
 event({'event':'run_start',**r});t=time.perf_counter()
 try:
  proc=subprocess.run(cmd,cwd=REPO,env=env,capture_output=True,text=True,timeout=timeout)
  r.update(cold_seconds=time.perf_counter()-t,returncode=proc.returncode,stdout=proc.stdout,stderr=proc.stderr,status='ok' if proc.returncode==0 else 'failed')
  if proc.returncode==0:
   meta_path=Path(str(prefix)+'.json');pred_path=Path(str(prefix)+'.pred.npy')
   r.update(metadata=json.loads(meta_path.read_text()),prediction_path=str(pred_path.relative_to(REPO)),prediction_sha256=sha(pred_path))
 except subprocess.TimeoutExpired as exc:
  r.update(cold_seconds=time.perf_counter()-t,status='timeout',stdout=str(exc.stdout),stderr=str(exc.stderr))
 record.write_text(json.dumps(r,indent=2)+'\n');event({'event':'run_end',**r})
 print(json.dumps({'run_id':run_id,'status':r['status'],'cold_seconds':r['cold_seconds'],'accuracy':r.get('metadata',{}).get('accuracy')}),flush=True)
 return r

def predictions(r):
 p=REPO/r['prediction_path']
 if sha(p)!=r['prediction_sha256']:raise ValueError('Prediction overwritten')
 return np.load(p,allow_pickle=False)

def compare(b,m):
 if b['status']!='ok' or m['status']!='ok':raise ValueError('Cannot compare failed runs')
 if b['prediction_path']==m['prediction_path']:raise ValueError('Shared prediction path')
 verify_frozen();t=time.perf_counter()
 with np.load(ART/'splits.npz',allow_pickle=False) as z:idx=z[b['split']]
 y=labels(DATA/'t10k-labels-idx1-ubyte.gz')[idx]
 out=evaluate(y,predictions(b),predictions(m));common=time.perf_counter()-t
 out.update(baseline_run_id=b['run_id'],method_run_id=m['run_id'],baseline_engine=b['engine'],method_engine=m['engine'],block=m['block'],baseline_cold_seconds=b['cold_seconds'],method_cold_seconds=m['cold_seconds'],quality_comparison_seconds=common,baseline_endpoint_seconds=b['cold_seconds']+common,method_endpoint_seconds=m['cold_seconds']+common)
 out['speedup']=out['baseline_endpoint_seconds']/out['method_endpoint_seconds'];event({'event':'pair_quality',**out});return out

def write_csv(path,rows):
 if not rows:return
 with Path(path).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def summary(rows):
 b=np.array([r['baseline_endpoint_seconds'] for r in rows]);m=np.array([r['method_endpoint_seconds'] for r in rows]);rng=np.random.default_rng(20261017)
 ix=rng.integers(0,len(rows),size=(10000,len(rows)));bs=b[ix].sum(1)/m[ix].sum(1)
 return {'n_pairs':len(rows),'speedup_ratio_of_sums':float(b.sum()/m.sum()),'paired_bootstrap_95ci':np.quantile(bs,[.025,.975]).tolist(),'baseline_mean_seconds':float(b.mean()),'method_mean_seconds':float(m.mean()),'baseline_range_seconds':[float(b.min()),float(b.max())],'method_range_seconds':[float(m.min()),float(m.max())],'baseline_sd_seconds':float(b.std(ddof=1)) if len(b)>1 else 0.,'method_sd_seconds':float(m.std(ddof=1)) if len(m)>1 else 0.,'all_quality_pass':all(r['quality_pass'] for r in rows),'baseline_accuracy':rows[0]['baseline_accuracy'],'candidate_accuracy':rows[0]['candidate_accuracy'],'min_label_agreement':min(r['label_agreement'] for r in rows),'statistical_scope':'timing variability on ONE fixed dataset; not independent data uncertainty'}
