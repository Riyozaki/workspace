"""Ready baseline inference, no custom optimized kernel code."""
from __future__ import annotations
import argparse,json,resource,time
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits,threadpool_info
from .data import ART,load_split

def predict(engine,x):
 if engine in ('native','threaded'):
  import joblib
  model=joblib.load(ART/'model.joblib')
  if engine=='native':return model.predict(x)
  from concurrent.futures import ThreadPoolExecutor
  chunks=np.array_split(x,2)
  with ThreadPoolExecutor(max_workers=2) as pool:return np.concatenate(list(pool.map(model.predict,chunks)))
 if engine=='onnx':
  import onnxruntime as ort
  opt=ort.SessionOptions();opt.intra_op_num_threads=2;opt.inter_op_num_threads=1;opt.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_ALL
  session=ort.InferenceSession(str(ART/'model.onnx'),sess_options=opt,providers=['CPUExecutionProvider'])
  return np.asarray(session.run([session.get_outputs()[0].name],{session.get_inputs()[0].name:x.astype(np.float32)})[0]).ravel()
 raise ValueError(engine)

def main():
 p=argparse.ArgumentParser();p.add_argument('--engine',choices=['native','threaded','onnx'],required=True);p.add_argument('--split',choices=['validation','holdout'],required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 pred_path=Path(str(a.output)+'.pred.npy');meta_path=Path(str(a.output)+'.json')
 if pred_path.exists() or meta_path.exists():raise FileExistsError(a.output)
 a.output.parent.mkdir(parents=True,exist_ok=True)
 t=time.perf_counter()
 with threadpool_limits(limits=2):
  t0=time.perf_counter();x,y=load_split(a.split);read=time.perf_counter()-t0
  t0=time.perf_counter();pred=predict(a.engine,x);infer=time.perf_counter()-t0
  if pred.shape!=y.shape or not np.isin(pred,np.arange(10)).all():raise ValueError('Invalid predictions')
  acc=float(np.mean(pred==y));np.save(pred_path,pred)
  meta={'engine':a.engine,'split':a.split,'n':len(y),'accuracy':acc,'read_preprocess_seconds':read,'load_model_predict_seconds':infer,'internal_seconds':time.perf_counter()-t,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'threadpools':threadpool_info()}
  meta_path.write_text(json.dumps(meta,indent=2)+'\n')
 print(json.dumps(meta),flush=True)
if __name__=='__main__':main()
