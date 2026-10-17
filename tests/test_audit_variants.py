import numpy as np
import pytest
from threadpoolctl import threadpool_limits
from tensor_gp.dense import DenseGP
from tensor_gp.dense_fortran import DenseFortranGP
from tensor_gp.spectral import SpectralGP
from tensor_gp.spectral_numpy import NumpySpectralGP


@pytest.mark.parametrize("shape", [(4, 7), (16, 11), (32, 24)])
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_audit_variants_identical(shape, seed):
    with threadpool_limits(limits=1):
        rng = np.random.default_rng(seed)
        axes = [np.sort(rng.uniform(size=n)) for n in shape]
        y = rng.normal(size=np.prod(shape))
        test = rng.uniform(size=(43, 2))
        ref = DenseGP().fit(axes, y)
        rm, rv = ref.predict(test)
        for cls in (DenseFortranGP, SpectralGP, NumpySpectralGP):
            model = cls().fit(axes, y)
            mean, variance = model.predict(test)
            np.testing.assert_allclose(mean, rm, atol=2e-8, rtol=2e-8)
            np.testing.assert_allclose(variance, rv, atol=1e-9, rtol=1e-8)
            if cls is DenseFortranGP:
                np.testing.assert_array_equal(model.chol[0], ref.chol[0])


def test_primary_protocol_unchanged():
    from tensor_gp.benchmark import read_protocol
    p = read_protocol()
    assert p["primary_case"]["train_size"] == 8192
    assert p["quality"]["noninferiority_absolute_tolerance"] == 1e-7
