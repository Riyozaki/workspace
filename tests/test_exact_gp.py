"""Independent correctness tests, not used for choosing hyperparameters."""
import numpy as np
import pytest
from scipy.linalg import cho_solve
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF
from threadpoolctl import threadpool_limits

from tensor_gp.data import load_dataset, make_dataset
from tensor_gp.dense import DenseGP
from tensor_gp.kernels import cross_factors, kernel_factors, row_tensor_product
from tensor_gp.spectral import SpectralGP


@pytest.fixture(autouse=True)
def single_thread_test():
    with threadpool_limits(limits=1):
        yield


@pytest.mark.parametrize("shape", [(3, 4), (7, 5), (16, 12)])
@pytest.mark.parametrize("seed", [0, 1, 2])
@pytest.mark.parametrize("signal", [0.3, 1.0, 2.5])
def test_matches_dense_and_residual(shape, seed, signal):
    rng = np.random.default_rng(seed)
    axes = [np.sort(rng.uniform(size=n)) for n in shape]
    y = rng.normal(size=np.prod(shape))
    x = rng.uniform(-0.2, 1.2, size=(31, 2))
    kwargs = dict(signal_variance=signal, noise_variance=0.0025)
    dense, spectral = DenseGP(**kwargs).fit(axes, y), SpectralGP(**kwargs).fit(axes, y)
    dm, dv = dense.predict(x)
    sm, sv = spectral.predict(x)
    np.testing.assert_allclose(sm, dm, atol=1e-8, rtol=1e-8)
    np.testing.assert_allclose(sv, dv, atol=1e-9, rtol=1e-8)
    kx, ky = kernel_factors(axes, (0.18, 0.23), signal)
    alpha = spectral.solve(y)
    residual = np.kron(kx, ky) @ alpha + 0.0025 * alpha - y
    assert np.linalg.norm(residual) / np.linalg.norm(y) < 1e-9
    np.testing.assert_allclose(alpha, cho_solve(dense.chol, y), atol=1e-6, rtol=1e-8)
    assert np.min(sv) >= 0


@pytest.mark.parametrize("noise", [1e-6, 0.0025, 0.1])
def test_independent_sklearn_reference(noise):
    rng = np.random.default_rng(11)
    axes = [np.linspace(0, 1, 12), np.linspace(0, 1, 9)]
    train_x = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 2)
    y = rng.normal(size=len(train_x))
    x = rng.uniform(size=(51, 2))
    kernel = ConstantKernel(1.0, "fixed") * RBF([0.18, 0.23], "fixed")
    ref = GaussianProcessRegressor(kernel=kernel, alpha=noise, optimizer=None, normalize_y=False)
    ref.fit(train_x, y)
    mean, std = ref.predict(x, return_std=True)
    for cls in (DenseGP, SpectralGP):
        m, v = cls(noise_variance=noise).fit(axes, y).predict(x)
        np.testing.assert_allclose(m, mean, atol=2e-7, rtol=2e-7)
        np.testing.assert_allclose(v, std**2, atol=1e-8, rtol=1e-7)


def test_cross_order_and_separability():
    axes = [np.array([0.1, 0.9]), np.array([0.2, 0.4, 0.8])]
    x = np.array([[0.3, 0.5], [0.6, 0.7]])
    actual = row_tensor_product(cross_factors(x, axes, (0.18, 0.23), 1.7))
    grid = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 2)
    diff = (x[:, None, :] - grid[None, :, :]) / np.array([0.18, 0.23])
    expected = 1.7 * np.exp(-0.5 * np.sum(diff**2, axis=-1))
    np.testing.assert_allclose(actual, expected, rtol=1e-14, atol=1e-14)


def test_fixture_reproducibility_and_disjointness(tmp_path):
    make_dataset(tmp_path / "a.npz", (11, 7), 29, 17)
    make_dataset(tmp_path / "b.npz", (11, 7), 29, 17)
    da, db = load_dataset(tmp_path / "a.npz"), load_dataset(tmp_path / "b.npz")
    for a, b in zip(da[0] + list(da[1:]), db[0] + list(db[1:]), strict=True):
        np.testing.assert_array_equal(a, b)
    axes, _, test_x, *_ = da
    grid = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 2)
    assert not np.any(np.all(grid[:, None] == test_x[None], axis=-1))


def test_invalid_structures_rejected():
    with pytest.raises(ValueError):
        SpectralGP(noise_variance=0)
    with pytest.raises(ValueError):
        SpectralGP().fit([np.arange(3), np.arange(4)], np.ones(11))
    with pytest.raises(ValueError):
        SpectralGP(lengthscales=(1,)).fit([np.arange(3)], np.ones(3))
