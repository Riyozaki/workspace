import ctypes
import numpy as np
import pytest
from competition50x.data import ART


@pytest.mark.parametrize('nq,ns',[(1,1),(7,15),(8,16),(9,17),(17,33)])
def test_fused_rbf_vs_exact_integer_distance(nq,ns):
 rng=np.random.default_rng(911+nq+ns)
 x=rng.integers(0,256,(nq,784),dtype=np.uint8);sv=rng.integers(0,256,(ns,784),dtype=np.uint8)
 x[0]=255;sv[0]=255
 padded=np.zeros((((ns+15)//16)*16,784),dtype=np.int8);padded[:ns]=(sv.astype(np.int16)-128).astype(np.int8)
 pack=np.ascontiguousarray(padded.reshape(-1,16,196,4).transpose(0,2,1,3));s=sv.astype(np.int32);norm=np.einsum('ij,ij->i',s,s,dtype=np.int32)
 out=np.empty((nq,ns),dtype=np.float32);lib=ctypes.CDLL(str(ART/'libu8gemm.so'));lib.u8_rbf.argtypes=[ctypes.c_void_p]*4+[ctypes.c_int]*3+[ctypes.c_double]
 gamma=.010234694240516045
 assert lib.u8_rbf(x.ctypes.data,pack.ctypes.data,norm.ctypes.data,out.ctypes.data,nq,ns,784,gamma)==0
 a=x.astype(np.int64);b=sv.astype(np.int64);dist=(a*a).sum(1)[:,None]+(b*b).sum(1)[None,:]-2*a@b.T
 ref=np.exp(-gamma*dist/65025.)
 np.testing.assert_allclose(out,ref,rtol=3e-6,atol=2e-7);assert out[0,0]==1.


def test_fused_real_validation_agreement():
 from competition50x.data import load_split
 from competition50x.inference import Compact
 import joblib
 model=joblib.load(ART/'model.joblib');x,_=load_split('validation');x=x[:33]
 pred,s=Compact(fused32=True).predict(np.rint(x*255.).astype(np.uint8),128,True)
 np.testing.assert_array_equal(pred,model.predict(x))
 np.testing.assert_allclose(s,model.decision_function(x),atol=5e-4,rtol=5e-4)
