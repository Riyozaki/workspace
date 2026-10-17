"""Execute matched-step router ablation; select using development only."""
from __future__ import annotations
import hashlib,json,time
from pathlib import Path
import numpy as np
from .router import BudgetRouter,calibrate,metrics,ROOT


def load_data():return [json.loads(l) for l in (ROOT/'data/router_pilot.jsonl').read_text().splitlines() if l]


def main():
 rows=load_data();train=[r for r in rows if r['split']=='train'];dev=[r for r in rows if r['split']=='development'];test=[r for r in rows if r['split']=='holdout']
 assert not {r['family'] for r in train}&{r['family'] for r in test+dev}
 results=[];models={};t=time.perf_counter()
 for kind in ('linear','loop'):
  for seed in (0,1,2):
   m=BudgetRouter(kind,seed);fit=m.fit([r['prompt'] for r in train],[r['target'] for r in train]);d=calibrate(m,dev)
   results.append({'kind':kind,'seed':seed,'fit':fit,'development':d});models[(kind,seed)]=m
 family={k:{metric:float(np.mean([r['development'][metric] for r in results if r['kind']==k])) for metric in ('accuracy','macro_f1','fast_path_coverage')} for k in ('linear','loop')}
 selected=max(family,key=lambda k:(family[k]['fast_path_coverage'],family[k]['macro_f1'],-models[(k,0)].parameters))
 deployed=models[(selected,0)]
 # Record choice BEFORE evaluating the independent pilot holdout.
 choice={'kind':selected,'seed':0,'threshold':deployed.threshold,'rule':'largest development mean fast-path coverage after >=98% development precision gate; macroF1 then smaller model; fixed deploy seed0, not best seed','family_development_means':family,'dataset_sha256':hashlib.sha256((ROOT/'data/router_pilot.jsonl').read_bytes()).hexdigest(),'selected_at_unix':time.time()}
 (ROOT/'results/router_selection.json').write_text(json.dumps(choice,indent=2)+'\n')
 for r in results:r['holdout']=metrics(models[(r['kind'],r['seed'])],test)
 report={'scope':'SYNTHETIC INTENT ROUTER ONLY. No LM fine-tuning or new-language-architecture claim.','all_runs':results,'selection':choice,'deployed_holdout':metrics(deployed,test),'total_training_seconds':time.perf_counter()-t,'loop_beats_linear_development_macro_f1':family['loop']['macro_f1']>family['linear']['macro_f1'],'hardware_threads':1,'training_steps_per_run':450,'known_limits':'Small authored family split; softmax scores not calibrated probabilities. Repeated feedback will not produce a new blind holdout.'}
 deployed.save(ROOT/'models/budget_router.json',{'dataset_sha256':choice['dataset_sha256'],'published_holdout':report['deployed_holdout'],'trained_by':'local NumPy, not a remote API'})
 (ROOT/'results/router_ablation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()
