import numpy as np
import pytest
from sklearn.svm import SVC
from competition50x.inference import gemm,vote,Compact,coefficients
from competition50x.data import ART


@pytest.mark.parametrize('nclasses',[2,3,10])
def test_gemm_vs_independent_libsvm(nclasses):
 rng=np.random.default_rng(717+nclasses);x=rng.random((nclasses*8,13));y=np.repeat(np.arange(nclasses),8)
 model=SVC(C=10,gamma='scale',decision_function_shape='ovo').fit(x,y)
 q=rng.random((17,13));reference=model.predict(q);dec=model.decision_function(q).reshape(17,-1)
 p,s=gemm(q,model,8,np.float64,True)
 np.testing.assert_array_equal(p,reference);np.testing.assert_allclose(s,dec,atol=2e-10,rtol=2e-10)
 _,s32=gemm(q,model,8,np.float32,True);np.testing.assert_allclose(s32,dec,atol=5e-5,rtol=5e-5)


def test_compact_full_real_model_on_validation_only():
 from competition50x.data import load_split
 import joblib
 model=joblib.load(ART/'model.joblib');x,_=load_split('validation');x=x[:33]
 reference=model.predict(x);dec=model.decision_function(x)
 p,s=Compact().predict(np.rint(x*255.).astype(np.uint8),128,True)
 np.testing.assert_array_equal(p,reference);np.testing.assert_allclose(s,dec,atol=2e-8,rtol=2e-8)
