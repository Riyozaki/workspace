"""Secondary fixed-system request-size sensitivity, never changes primary."""
import json,os,random,subprocess,sys,time
from collections import defaultdict
import numpy as np
from .paths import ROOT,ART,DATA
from .clock import snapshot
from .primary import verify_method
from .data import labels
from .eval import evaluate
from .harness import write_csv,summary,event


def main():
 snapshot('Stage 10 — frozen-system batch-size counterexamples','SECONDARY only; no retuning. N=2/8/32/128/512/5000, validation prefixes, 3 repeats each, balanced order. Same frozen source/model; actual complete requests, no duplicated data to inflate primary.')
 verify_method();plan=[(n,r) for n in (2,8,32,128,512,5000) for r in range(3)];random.Random(20261017).shuffle(plan)
 with np.load(ART/'splits.npz',allow_pickle=False) as z:idx=z['validation']
 y=labels(DATA/'t10k-labels-idx1-ubyte.gz')[idx];rows=[];failures=[];env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
 records=ROOT/'results/batch_runs';records.mkdir(exist_ok=True)
 for n,rep in plan:
  pair={};order=['threaded','compact'] if rep%2==0 else ['compact','threaded']
  for e in order:
   prefix=ART/'batch_sweep'/f'n{n}_r{rep}_{e}';rp=records/f'n{n}_r{rep}_{e}.json'
   if rp.exists():raise FileExistsError(rp)
   verify_method();cmd=[sys.executable,'-m','competition50x.batch_worker','--engine',e,'--n',str(n),'--output',str(prefix)];t=time.perf_counter()
   p=subprocess.run(cmd,env=env,cwd=ROOT.parent,capture_output=True,text=True,timeout=180)
   r={'engine':e,'n':n,'repeat':rep,'cold_seconds':time.perf_counter()-t,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'prediction':str(prefix)+'.pred.npy'}
   rp.write_text(json.dumps(r,indent=2)+'\n');pair[e]=r;event({'event':'secondary_batch_run',**r})
  if any(r['returncode'] for r in pair.values()):failures.append({'n':n,'repeat':rep});continue
  t=time.perf_counter();q=evaluate(y[:n],np.load(pair['threaded']['prediction']),np.load(pair['compact']['prediction']));extra=time.perf_counter()-t
  q.update(n=n,repeat=rep,baseline_endpoint_seconds=pair['threaded']['cold_seconds']+extra,method_endpoint_seconds=pair['compact']['cold_seconds']+extra)
  q['speedup']=q['baseline_endpoint_seconds']/q['method_endpoint_seconds'];rows.append(q);write_csv(ROOT/'results/batch_sweep.csv',rows)
  print('Batch',n,'repeat',rep,'ratio',q['speedup'],'quality',q['quality_pass'],flush=True)
 groups=defaultdict(list)
 for r in rows:groups[str(r['n'])].append(r)
 out={'scope':'SECONDARY; fixed primary method/baseline, not best baseline per small batch','planned_pairs':18,'completed_pairs':len(rows),'failures':failures,'groups':{k:summary(v) for k,v in groups.items()}}
 (ROOT/'results/batch_sweep_summary.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2),flush=True)
if __name__=='__main__':main()
