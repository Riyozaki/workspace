"""Check exact objective and analytic gradient against an independent library."""
import json
from pathlib import Path
import numpy as np
import pytest
from scipy.optimize._numdiff import approx_derivative
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel
from threadpoolctl import threadpool_limits
from tensor_gp.hyperparameters import TensorObjective, TensorHyperGP, SklearnHyperGP
from tensor_gp.data import latent
from tensor_gp.experiments import ROOT


@pytest.mark.parametrize("seed", [0, 1, 2])
@pytest.mark.parametrize("sizes", [(6, 5), (12, 9)])
def test_objective_and_gradient(seed, sizes):
    with threadpool_limits(limits=1):
        rng = np.random.default_rng(seed)
        axes = [np.linspace(0, 1, n) for n in sizes]
        grid = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 2)
        y = latent(grid) + 0.05 * rng.normal(size=len(grid))
        y -= y.mean()
        theta = np.log([1.0, 0.18, 0.23, 0.0025])
        kernel = ConstantKernel(1.0, (0.01, 10)) * RBF([0.18, 0.23], (0.02, 1)) + WhiteKernel(0.0025, (0.0001, 0.1))
        ref = GaussianProcessRegressor(kernel=kernel, alpha=0, optimizer=None).fit(grid, y)
        lml, grad = ref.log_marginal_likelihood(theta, eval_gradient=True)
        fun = TensorObjective(axes, y)
        value, actual_grad = fun(theta)
        np.testing.assert_allclose(value, -lml, atol=2e-7, rtol=1e-8)
        np.testing.assert_allclose(actual_grad, -grad, atol=2e-5, rtol=2e-6)
        numerical = approx_derivative(lambda t: fun(t)[0], theta, method="3-point", rel_step=1e-5).ravel()
        np.testing.assert_allclose(actual_grad, numerical, atol=2e-5, rtol=2e-6)


def test_end_to_end_optimizer_equivalence_small():
    with threadpool_limits(limits=1):
        axes = [np.linspace(0, 1, 12), np.linspace(0, 1, 10)]
        grid = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 2)
        rng = np.random.default_rng(0)
        y = latent(grid) + 0.05 * rng.normal(size=len(grid)); y -= y.mean()
        test = rng.uniform(size=(25, 2))
        spec = json.loads((ROOT / "research/hyperparameter_protocol.json").read_text())
        dense = SklearnHyperGP(spec).fit(axes, y)
        fast = TensorHyperGP(spec).fit(axes, y)
        dm, dv = dense.predict(test)
        fm, fv = fast.predict(test)
        np.testing.assert_allclose(dm, fm, atol=1e-6, rtol=1e-6)
        np.testing.assert_allclose(dv, fv, atol=1e-6, rtol=1e-6)
        assert abs(dense.optimization.fun-fast.optimization.fun) < 1e-5
