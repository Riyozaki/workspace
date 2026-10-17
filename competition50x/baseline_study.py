"""Measure ready references FIRST, then lock the strongest eligible reference."""
import json,os,random,subprocess,sys,time
from .data import ROOT,ART
from .harness import run,compare,status,event,summary,REPO,RESULTS,verify_frozen
from .clock import snapshot

def main():
 verify_frozen();snapshot('Stage 2 — shared training and unmodified reference measurements','Protocol/evaluator sealed before 600 s. Custom predictor not yet implemented. All 60k real training observations; reference-family calibration precedes any optimization.')
 env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
 status(stage='training common model',measured_speedup=None,quality=None,verification_probability_percent=15,main_risk='Training/inference cost unknown; specialized runtime may remove most advantage; no method result exists.')
 t=time.perf_counter()
 with (RESULTS/'prepare_stdout.log').open('w') as log:
  try:p=subprocess.run([sys.executable,'-m','competition50x.prepare'],cwd=REPO,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=2700)
  except subprocess.TimeoutExpired:
   event({'event':'shared_training_timeout','seconds':time.perf_counter()-t});status(stage='shared training timeout',measured_speedup=None,quality=None,verification_probability_percent=0,main_risk='No completed reference');return
 if p.returncode:
  event({'event':'shared_training_failed','returncode':p.returncode});raise RuntimeError('See prepare_stdout.log')
 engines=['native','threaded']
 if (ART/'model.onnx').exists():engines.append('onnx')
 plan=[(e,i) for e in engines for i in range(3)];random.Random(20261017).shuffle(plan)
 (RESULTS/'baseline_plan.json').write_text(json.dumps(plan,indent=2)+'\n')
 records=[]
 for engine,i in plan:
  status(stage='measuring unmodified references',measured_speedup=None,quality=None,verification_probability_percent=25,main_risk='No custom candidate measured; fastest ready baseline not yet fixed.',completed_reference_runs=len(records))
  records.append(run(engine,'validation',f'baseline_{engine}_r{i}'))
 native=next((r for r in records if r['engine']=='native' and r['status']=='ok'),None)
 if native is None:raise RuntimeError('Native canonical reference did not complete')
 table={}
 for e in engines:
  runs=[r for r in records if r['engine']==e];ok=[r for r in runs if r['status']=='ok']
  # Calibration must use a distinct native replica even for its canonical run.
  # The shared-path guard remains strict for baseline-versus-method comparisons.
  gates=[compare(next(n for n in records if n['engine']=='native' and n['status']=='ok' and n['prediction_path']!=r['prediction_path']),r) for r in ok]
  table[e]={'n_attempted':len(runs),'n_completed':len(ok),'mean_cold_seconds':sum(r['cold_seconds'] for r in ok)/len(ok) if ok else None,'eligible':len(ok)==3 and all(g['quality_pass'] for g in gates),'quality_checks':gates}
 selected=min((e for e in engines if table[e]['eligible']),key=lambda e:table[e]['mean_cold_seconds'])
 result={'selected_engine':selected,'criterion':'minimum mean of all 3 pre-optimization cold validation runs among quality-eligible ready references','references':table,'selected_at_unix':time.time()}
 (RESULTS/'baseline_selected.json').write_text(json.dumps(result,indent=2)+'\n');event({'event':'baseline_locked',**result})
 status(stage='strong baseline locked; ready for custom predictor',measured_speedup=None,quality=None,baseline_engine=selected,baseline_mean_seconds=table[selected]['mean_cold_seconds'],verification_probability_percent=35,main_risk='No custom method measured yet; no transfer or 50x assertion.')
 print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()
