"""One-time model-format/native-library preparation; separately timed/disclosed."""
from __future__ import annotations
import json,subprocess,time
import numpy as np
from .data import ROOT,ART,digest
from .harness import verify_frozen,event

def main():
 verify_frozen()
 if not (ROOT/'results/baseline_selected.json').exists():raise RuntimeError('Baseline must be locked before optimization')
 t=time.perf_counter();command=['cc','-O3','-shared','-fPIC','-fopenmp','-mavx512vnni','-mavx512bw','-mavx512vl',str(ROOT/'u8gemm.c'),'-o',str(ART/'libu8gemm.so'),'-lm']
 proc=subprocess.run(command,capture_output=True,text=True,check=True);compile_time=time.perf_counter()-t
 from .inference import coefficients
 t=time.perf_counter()
 with np.load(ART/'model_raw.npz',allow_pickle=False) as z:
  sv=z['support_vectors'];dual=z['dual_coef'];ns=z['n_support'];intercept=z['intercept'];classes=z['classes'];gamma=z['gamma']
 u=np.rint(sv*255.).astype(np.uint8)
 if not np.array_equal(u.astype(np.float64)/255.,sv):raise ValueError('SVs are not exactly original uint8 pixels / 255')
 nsv,d=u.shape
 if d!=784:raise ValueError(d)
 padded=np.zeros((((nsv+15)//16)*16,784),dtype=np.int8)
 padded[:nsv]=(u.astype(np.int16)-128).astype(np.int8)
 packed=np.ascontiguousarray(padded.reshape(-1,16,196,4).transpose(0,2,1,3))
 ui=u.astype(np.int32);svnorm=np.einsum('ij,ij->i',ui,ui,dtype=np.int32)
 coef=coefficients(dual,ns)
 np.savez(ART/'model_compact.npz',packed=packed,svnorm=svnorm,coef=coef,intercept=intercept,classes=classes,gamma=gamma)
 r={'compile_seconds':compile_time,'packing_seconds':time.perf_counter()-t,'compile_command':command,'compiler':subprocess.check_output(['cc','--version'],text=True).splitlines()[0],'n_support':nsv,'source_model_sha256':digest(ART/'model_raw.npz'),'compact_model_sha256':digest(ART/'model_compact.npz'),'compact_bytes':(ART/'model_compact.npz').stat().st_size,'library_sha256':digest(ART/'libu8gemm.so'),'exact_uint8_roundtrip':True,'scope':'one-time conversion/build, not hidden in per-request inference; non-amortized calculation reported separately'}
 (ROOT/'results/compact_preparation.json').write_text(json.dumps(r,indent=2)+'\n');event({'event':'compact_model_prepared',**r});print(json.dumps(r,indent=2),flush=True)
if __name__=='__main__':main()
