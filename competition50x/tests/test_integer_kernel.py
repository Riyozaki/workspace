import ctypes
import numpy as np
import pytest
from competition50x.data import ART


@pytest.mark.parametrize('nq,ns',[(1,1),(7,15),(8,16),(9,17),(17,33)])
def test_integer_tail_and_exactness(nq,ns):
 rng=np.random.default_rng(550+nq+ns)
 x=rng.integers(0,256,(nq,784),dtype=np.uint8);sv=rng.integers(0,256,(ns,784),dtype=np.uint8)
 x[0]=255;sv[0]=255
 padded=np.zeros((((ns+15)//16)*16,784),dtype=np.int8);padded[:ns]=(sv.astype(np.int16)-128).astype(np.int8)
 pack=np.ascontiguousarray(padded.reshape(-1,16,196,4).transpose(0,2,1,3))
 out=np.empty((nq,ns),dtype=np.int32)
 lib=ctypes.CDLL(str(ART/'libu8gemm.so'));lib.u8_dot.argtypes=[ctypes.c_void_p]*3+[ctypes.c_int]*3
 assert lib.u8_dot(x.ctypes.data,pack.ctypes.data,out.ctypes.data,nq,ns,784)==0
 exact=x.astype(np.int64)@sv.astype(np.int64).T
 np.testing.assert_array_equal(out,exact);assert out[0,0]==784*255*255
