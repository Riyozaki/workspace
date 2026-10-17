import numpy as np
import pytest
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF
from threadpoolctl import threadpool_limits
from tensor_gp.masked import DenseMaskedGP, PCGMaskedGP, observed_subset


@pytest.mark.parametrize("missing", [0.0, 0.1, 0.5, 0.9])
@pytest.mark.parametrize("seed", [0, 1])
def test_masked_dense_pcg_and_sklearn(missing, seed):
    with threadpool_limits(limits=1):
        axes = [np.linspace(0, 1, 11), np.linspace(0, 1, 9)]
        grid = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 2)
        obs = observed_subset(len(grid), missing, seed)
        rng = np.random.default_rng(seed)
        y = rng.normal(size=len(obs))
        x = rng.uniform(size=(11, 2))
        dense = DenseMaskedGP().fit(axes, obs, y)
        pcg = PCGMaskedGP().fit(axes, obs, y)
        dm, dv = dense.predict(x)
        pm, pv = pcg.predict(x)
        kernel = ConstantKernel(1, "fixed") * RBF([0.18, 0.23], "fixed")
        ref = GaussianProcessRegressor(kernel=kernel, alpha=0.0025, optimizer=None).fit(grid[obs], y)
        rm, rs = ref.predict(x, return_std=True)
        np.testing.assert_allclose(dm, rm, atol=1e-8, rtol=1e-8)
        np.testing.assert_allclose(dv, rs**2, atol=1e-9, rtol=1e-8)
        np.testing.assert_allclose(pm, dm, atol=1e-7, rtol=1e-8)
        np.testing.assert_allclose(pv, dv, atol=1e-8, rtol=1e-7)
        assert max(pcg.relative_residuals) < 1e-8
        if missing == 0:
            assert max(pcg.iterations) <= 3


def test_mask_independent_sorted_and_repeatable():
    np.testing.assert_array_equal(observed_subset(1000, 0.1, 7), observed_subset(1000, 0.1, 7))
    obs = observed_subset(1000, 0.1, 7)
    assert len(obs) == 900
    assert np.all(np.diff(obs) > 0)
