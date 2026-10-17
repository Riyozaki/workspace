"""SECONDARY batch-size requests; original frozen predictor implementations."""
import argparse,json,resource,time
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits,threadpool_info
from .paths import ART,DATA


def main():
 p=argparse.ArgumentParser();p.add_argument('--engine',choices=['threaded','compact'],required=True);p.add_argument('--n',type=int,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.n not in (2,8,32,128,512,5000):raise ValueError(a.n)
 pred_path=Path(str(a.output)+'.pred.npy');meta=Path(str(a.output)+'.json')
 if pred_path.exists() or meta.exists():raise FileExistsError(a.output)
 a.output.parent.mkdir(parents=True,exist_ok=True);t=time.perf_counter()
 with threadpool_limits(limits=2):
  if a.engine=='compact':
   from . import request_data as loader
  else:
   from . import data as loader
  with np.load(ART/'splits.npz',allow_pickle=False) as z:idx=z['validation'][:a.n]
  raw=loader.images(DATA/'t10k-images-idx3-ubyte.gz')[idx];y=loader.labels(DATA/'t10k-labels-idx1-ubyte.gz')[idx]
  if a.engine=='compact':
   from .inference import Compact
   pred=Compact(fused32=True).predict(raw,128)
  else:
   from .reference_worker import predict
   pred=predict('threaded',raw.astype(np.float64)/255.)
  np.save(pred_path,pred)
  result={'engine':a.engine,'n':a.n,'accuracy':float(np.mean(pred==y)),'internal_seconds':time.perf_counter()-t,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'threadpools':threadpool_info()}
  meta.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result),flush=True)
if __name__=='__main__':main()
