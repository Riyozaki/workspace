"""All predeclared blocks, all three systems, all three repetitions; val only."""
from __future__ import annotations
import argparse,json,random
from collections import defaultdict
from .clock import snapshot,elapsed
from .data import ROOT
from .harness import RESULTS,run,compare,write_csv,summary,status,event

def main():
 p=argparse.ArgumentParser();p.add_argument('--label',default='validation_r1');p.add_argument('--engine',choices=['all','gemm64','gemm32','compact'],default='all');a=p.parse_args()
 snapshot('Stage 4 — full validation requests',f'Round {a.label}; full 5000 validation examples, not holdout. Every declared block/repetition is retained. No primary result yet.')
 selected=json.loads((RESULTS/'baseline_selected.json').read_text());e=selected['selected_engine'];mean=selected['references'][e]['mean_cold_seconds']
 b=json.loads((RESULTS/'runs'/f'baseline_{e}_r0.json').read_text())
 engines=['gemm64','gemm32','compact'] if a.engine=='all' else [a.engine]
 plan=[(engine,block,r) for engine in engines for block in (128,256,512,1024,2048) for r in range(3)];random.Random(20261017).shuffle(plan)
 plan_path=RESULTS/f'{a.label}_plan.json'
 if plan_path.exists():raise FileExistsError(plan_path)
 plan_path.write_text(json.dumps(plan,indent=2)+'\n');rows=[];failures=[];groups=defaultdict(list)
 for engine,block,rep in plan:
  if elapsed()>5100:
   event({'event':'validation_time_stop','label':a.label,'remaining_unstarted':len(plan)-len(rows)-len(failures)});break
  r=run(engine,'validation',f'{a.label}_{engine}_b{block}_r{rep}',block)
  if r['status']!='ok':failures.append({'engine':engine,'block':block,'repeat':rep,'status':r['status']});continue
  row=compare(b,r);row['baseline_endpoint_seconds']=mean+row['quality_comparison_seconds'];row['speedup']=row['baseline_endpoint_seconds']/row['method_endpoint_seconds'];row['repeat']=rep;row['baseline_timing_scope']='3-run pre-optimization validation mean; secondary only'
  rows.append(row);groups[f'{engine}:{block}'].append(row);write_csv(RESULTS/f'{a.label}.csv',rows)
  candidates={k:summary(v) for k,v in groups.items() if len(v)==3 and all(x['quality_pass'] for x in v)}
  if candidates:
   best=min(candidates,key=lambda k:candidates[k]['method_mean_seconds']);s=candidates[best]
   status(stage='validation optimization only; holdout still unscored',measured_speedup=s['speedup_ratio_of_sums'],quality={'validation_accuracy':s['candidate_accuracy'],'agreement':s['min_label_agreement'],'all_pass':s['all_quality_pass']},best_validation=best,verification_probability_percent=75,main_risk='Validation-selection optimism; final holdout still unread; inference excludes common training and one-time export/build.')
 out={'scope':'SECONDARY validation; not final holdout result','planned_runs':len(plan),'completed_runs':len(rows),'failures':failures,'groups':{k:summary(v) for k,v in groups.items()}}
 (RESULTS/f'{a.label}_summary.json').write_text(json.dumps(out,indent=2)+'\n');event({'event':'validation_round_complete',**out});print(json.dumps(out,indent=2),flush=True)
if __name__=='__main__':main()
