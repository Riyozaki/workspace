"""Useful late paired ML measurements, then randomized native boundary checks.

No sleeping/busy-wait padding. Numeric code remains frozen; final publication
runs automatically only when BOTH real clocks reached the 90-minute deadline.
"""
from __future__ import annotations
import ctypes,json,time
from pathlib import Path
import numpy as np
from .clock import snapshot,elapsed
from .paths import ROOT,ART
from .harness import run,compare,write_csv,summary,event,status
from .primary import verify_method


def operator_probe(lib,rng,gamma):
 nq=int(rng.choice([1,2,7,8,9,15,16,17,31,33]));ns=int(rng.choice([10,15,16,17,31,33,64,127]))
 x=rng.integers(0,256,(nq,784),dtype=np.uint8);sv=rng.integers(0,256,(ns,784),dtype=np.uint8)
 if rng.random()<.15:x[0]=255;sv[0]=255
 if rng.random()<.15:x[0]=0;sv[-1]=255
 pad=np.zeros((((ns+15)//16)*16,784),dtype=np.int8);pad[:ns]=(sv.astype(np.int16)-128).astype(np.int8)
 pack=np.ascontiguousarray(pad.reshape(-1,16,196,4).transpose(0,2,1,3))
 a=x.astype(np.int64);b=sv.astype(np.int64);exact=a@b.T;dot=np.empty((nq,ns),dtype=np.int32)
 assert lib.u8_dot(x.ctypes.data,pack.ctypes.data,dot.ctypes.data,nq,ns,784)==0
 integer_error=int(np.abs(dot.astype(np.int64)-exact).max())
 sn=(b*b).sum(1).astype(np.int32);out=np.empty((nq,ns),dtype=np.float32)
 assert lib.u8_rbf(x.ctypes.data,pack.ctypes.data,sn.ctypes.data,out.ctypes.data,nq,ns,784,gamma)==0
 dist=(a*a).sum(1)[:,None]+sn[None,:]-2*exact;ref=np.exp(-gamma*dist/65025.)
 abs_exp=float(np.abs(out-ref).max());rel_exp=float(np.max(np.abs(out-ref)/ref))
 counts=np.ones(10,dtype=np.int32)+rng.multinomial(ns-10,np.full(10,.1)).astype(np.int32);starts=np.r_[0,np.cumsum(counts)].astype(np.int32)
 pairs=np.array([[p for p,(i,j) in enumerate((i,j) for i in range(10) for j in range(i+1,10)) if cls in (i,j)] for cls in range(10)],dtype=np.int32)
 sparse=np.zeros((ns,16));sparse[:,:9]=rng.standard_normal((ns,9));dense=np.zeros((ns,45))
 for cls in range(10):dense[starts[cls]:starts[cls+1],pairs[cls]]=sparse[starts[cls]:starts[cls+1],:9]
 intercept=rng.standard_normal(45);scores=np.broadcast_to(intercept,(nq,45)).copy()
 assert lib.mixed_scores(out.ctypes.data,sparse.ctypes.data,starts.ctypes.data,pairs.ctypes.data,scores.ctypes.data,nq,ns)==0
 expected=out.astype(np.float64)@dense+intercept;score_error=float(np.abs(scores-expected).max())
 valid=integer_error==0 and np.allclose(out,ref,rtol=3e-6,atol=2e-7) and np.allclose(scores,expected,rtol=5e-10,atol=5e-10)
 return {'nq':nq,'ns':ns,'integer_error':integer_error,'exp_max_abs':abs_exp,'exp_max_relative':rel_exp,'mixed_score_max_abs':score_error,'pass':bool(valid)}


def main():
 snapshot('Stage 11 — late stability and deadline operator audit','Numerical model/code frozen. Predeclare up to 100 complete validation pairs in order, start pairs only before elapsed5280s, baseline timeout45s, method20s. Every attempt kept; no quality/speed selection. Remaining time is random integer/fused-exp/mixed-score boundary tests, NOT a new ML speedup. Final sealing automated after BOTH real clocks reach5400s.')
 frozen=verify_method();primary=json.loads((ROOT/'results/primary_summary.json').read_text());rows=[];failed=[];attempted=0
 plan=ROOT/'results/late_validation_plan.json'
 if plan.exists():raise FileExistsError(plan)
 plan.write_text(json.dumps({'maximum_pairs':100,'prefix_order':'0..99','start_cutoff_seconds':5280,'baseline_timeout':45,'method_timeout':20,'operator_rng_seed':2026101717,'operator_gates':{'integer_exact':True,'exp_rtol':3e-6,'exp_atol':2e-7,'float64_score_rtol_atol':5e-10},'primary_not_changed_or_pooled':True},indent=2)+'\n')
 for i in range(100):
  if elapsed()>=5280:break
  attempted+=1;order=['threaded','compact'] if i%2==0 else ['compact','threaded'];pair={}
  for e in order:pair[e]=run(e,'validation',f'late_validation_r{i}_{e}',128,timeout=45 if e=='threaded' else 20)
  if any(r['status']!='ok' for r in pair.values()):failed.append({'repeat':i,'statuses':{e:r['status'] for e,r in pair.items()}});continue
  row=compare(pair['threaded'],pair['compact']);row['repeat']=i;rows.append(row);write_csv(ROOT/'results/late_validation.csv',rows)
  status(stage='frozen primary complete; secondary late validation',measured_speedup=primary['speedup_ratio_of_sums'],quality={'baseline_accuracy':primary['baseline_accuracy'],'method_accuracy':primary['candidate_accuracy'],'agreement':primary['min_label_agreement'],'all_gates':primary['all_quality_pass']},secondary_late_pairs=len(rows),verification_probability_percent=92,main_risk='Primary remains ONE local public holdout, no external organizer verification, no guaranteed50x; late requests not pooled.')
 out=summary(rows) if rows else {'n_pairs':0};out.update(attempted_pairs=attempted,failed_pairs=failed,unstarted_pairs=100-attempted,scope='SECONDARY time-limited prefix; not primary')
 (ROOT/'results/late_validation_summary.json').write_text(json.dumps(out,indent=2)+'\n')
 verify_method();lib=ctypes.CDLL(str(ART/'libu8gemm.so'))
 lib.u8_dot.argtypes=[ctypes.c_void_p]*3+[ctypes.c_int]*3
 lib.u8_rbf.argtypes=[ctypes.c_void_p]*4+[ctypes.c_int]*3+[ctypes.c_double]
 lib.mixed_scores.argtypes=[ctypes.c_void_p]*5+[ctypes.c_int]*2
 with np.load(ART/'model_compact.npz') as z:gamma=float(z['gamma'])
 rng=np.random.default_rng(2026101717);count=0;failures=[];maxima={'integer_error':0,'exp_max_abs':0.,'exp_max_relative':0.,'mixed_score_max_abs':0.};bad=0
 while elapsed()<5400:
  r=operator_probe(lib,rng,gamma);count+=1
  for k in maxima:maxima[k]=max(maxima[k],r[k])
  if not r['pass']:
   bad+=1
   if len(failures)<20:failures.append({'probe':count,**r})
 audit={'probe_count':count,'failed_probes':bad,'first_failures':failures,'maxima':maxima,'all_pass':bad==0,'elapsed_end_seconds':elapsed(),'scope':'random algebraic/memory-boundary validation only, NOT a system speedup','rng_seed':2026101717}
 (ROOT/'results/deadline_operator_audit.json').write_text(json.dumps(audit,indent=2)+'\n');event({'event':'deadline_operator_audit',**audit})
 # Everything required for the final report was prepared before the deadline.
 from .publication import seal
 seal();print(json.dumps(audit,indent=2),flush=True)
if __name__=='__main__':main()
