"""One shared real model training; excluded from inference-only headline."""
from __future__ import annotations
import gc,hashlib,json,resource,time,traceback
import joblib,numpy as np
from sklearn.svm import SVC
from threadpoolctl import threadpool_limits,threadpool_info
from .data import ROOT,ART,DATA,download,create_splits,images,labels,digest

def main():
 download();create_splits();results=ROOT/'results';results.mkdir(exist_ok=True)
 result={'scope':'shared model preparation, NOT a measured inference speedup'}
 x=images(DATA/'train-images-idx3-ubyte.gz').astype(np.float64)/255.;y=labels(DATA/'train-labels-idx1-ubyte.gz')
 params=dict(C=10.,kernel='rbf',gamma='scale',shrinking=True,probability=False,tol=.001,cache_size=1536,max_iter=-1,decision_function_shape='ovo',break_ties=False,random_state=20261017)
 model=SVC(**params)
 print('Training unchanged SVC on',x.shape,'C=10 gamma=scale',flush=True)
 t=time.perf_counter()
 with threadpool_limits(limits=2):model.fit(x,y)
 result.update(train_seconds=time.perf_counter()-t,params=params,n_train=len(y),gamma=float(model._gamma),n_support=model.n_support_.tolist(),total_support=len(model.support_),n_iter=model.n_iter_.tolist())
 print('Training completed',result['train_seconds'],'support vectors',result['total_support'],flush=True)
 t=time.perf_counter();joblib.dump(model,ART/'model.joblib',compress=0);result['native_serialization_seconds']=time.perf_counter()-t
 t=time.perf_counter();np.savez(ART/'model_raw.npz',support_vectors=model.support_vectors_,dual_coef=model.dual_coef_,intercept=model.intercept_,n_support=model.n_support_,classes=model.classes_,gamma=np.array(model._gamma));result['raw_export_seconds']=time.perf_counter()-t
 result['artifacts']={name:{'sha256':digest(ART/name),'bytes':(ART/name).stat().st_size} for name in ('model.joblib','model_raw.npz')}
 (results/'training.json').write_text(json.dumps(result,indent=2)+'\n')
 del x,y;gc.collect()
 try:
  from skl2onnx import convert_sklearn
  from skl2onnx.common.data_types import FloatTensorType
  t=time.perf_counter();onnx=convert_sklearn(model,initial_types=[('X',FloatTensorType([None,784]))],options={id(model):{'zipmap':False}},target_opset=17)
  (ART/'model.onnx').write_bytes(onnx.SerializeToString());result['onnx_export_seconds']=time.perf_counter()-t
  result['artifacts']['model.onnx']={'sha256':digest(ART/'model.onnx'),'bytes':(ART/'model.onnx').stat().st_size}
  print('ONNX export completed',result['onnx_export_seconds'],flush=True)
 except Exception as e:
  result['onnx_export_failure']=repr(e);(results/'onnx_export_failure.txt').write_text(traceback.format_exc());print('ONNX export failed',repr(e),flush=True)
 result['peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024;result['threadpools']=threadpool_info()
 (results/'training.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()
