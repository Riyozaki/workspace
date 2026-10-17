import numpy as np
import pytest
from competition50x.inference import Compact


@pytest.mark.parametrize('nq',[1,7,8,9,17])
def test_native_mixed_float64_reduction(nq):
 m=Compact(fused32=True);rng=np.random.default_rng(123+nq)
 k=rng.random((nq,m.nsv),dtype=np.float32)
 out=np.broadcast_to(m.intercept,(nq,45)).copy()
 assert m.lib.mixed_scores(k.ctypes.data,m.sparse.ctypes.data,m.starts.ctypes.data,m.pairs.ctypes.data,out.ctypes.data,nq,m.nsv)==0
 dense=np.zeros((m.nsv,45))
 for cls in range(10):dense[m.starts[cls]:m.starts[cls+1],m.pairs[cls]]=m.sparse[m.starts[cls]:m.starts[cls+1],:9]
 expected=k.astype(np.float64)@dense+m.intercept
 np.testing.assert_allclose(out,expected,atol=5e-10,rtol=5e-10)
