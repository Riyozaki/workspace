"""Cold inference request; prediction functions never receive targets."""
from __future__ import annotations
import argparse,json,resource,time
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits,threadpool_info
from .request_data import ART,DATA,images,labels,load_split
from .inference import gemm,Compact

def main():
 p=argparse.ArgumentParser();p.add_argument('--engine',choices=['gemm64','gemm32','compact'],required=True);p.add_argument('--split',choices=['validation','holdout'],required=True);p.add_argument('--block',type=int,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.block not in (128,256,512,1024,2048):raise ValueError(a.block)
 pred_path=Path(str(a.output)+'.pred.npy');meta_path=Path(str(a.output)+'.json')
 if pred_path.exists() or meta_path.exists():raise FileExistsError(a.output)
 a.output.parent.mkdir(parents=True,exist_ok=True);t=time.perf_counter()
 with threadpool_limits(limits=2):
  t0=time.perf_counter()
  if a.engine=='compact':
   with np.load(ART/'splits.npz',allow_pickle=False) as z:idx=z[a.split]
   x=images(DATA/'t10k-images-idx3-ubyte.gz')[idx];y=labels(DATA/'t10k-labels-idx1-ubyte.gz')[idx]
  else:x,y=load_split(a.split)
  read=time.perf_counter()-t0;t0=time.perf_counter()
  profile={}
  if a.engine=='compact':
   compact=Compact(fused32=True);pred=compact.predict(x,a.block);profile=compact.profile
  else:
   import joblib
   model=joblib.load(ART/'model.joblib')
   pred=gemm(x,model,a.block,np.float64 if a.engine=='gemm64' else np.float32)
  infer=time.perf_counter()-t0
  if pred.shape!=y.shape or not np.isin(pred,np.arange(10)).all():raise ValueError('Invalid predictions')
  acc=float(np.mean(pred==y));np.save(pred_path,pred)
  meta={'engine':a.engine,'split':a.split,'block':a.block,'n':len(y),'accuracy':acc,'read_preprocess_seconds':read,'load_model_predict_seconds':infer,'internal_seconds':time.perf_counter()-t,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'threadpools':threadpool_info(),'component_profile_secondary':profile}
  meta_path.write_text(json.dumps(meta,indent=2)+'\n')
 print(json.dumps(meta),flush=True)
if __name__=='__main__':main()
