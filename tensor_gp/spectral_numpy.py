"""Same full-rank algebra as SpectralGP, with a NumPy-only cold-start path.

Separate version: the original primary result is not rewritten or pooled.
This deliberately duplicates a small solver to avoid importing SciPy through a
base class. Tests check it against both dense implementations and SpectralGP.
"""
from time import perf_counter
import numpy as np
from .kernels import cross_factors, kernel_factors


class NumpySpectralGP:
    def __init__(self, lengthscales=(0.18, 0.23), signal_variance=1.0, noise_variance=0.0025):
        self.lengthscales = tuple(lengthscales)
        self.signal_variance = float(signal_variance)
        self.noise_variance = float(noise_variance)
        if self.noise_variance <= 0 or self.signal_variance <= 0:
            raise ValueError("Positive signal and noise variances are required")
        if any(ell <= 0 for ell in self.lengthscales):
            raise ValueError("Lengthscales must be positive")
        self.timings = {}

    def fit(self, axes, y):
        if len(axes) != 2 or len(self.lengthscales) != 2:
            raise ValueError("Two dimensional implementation")
        self.shape = tuple(len(a) for a in axes)
        if np.asarray(y).size != np.prod(self.shape):
            raise ValueError("Complete grid required")
        self.axes = axes
        t = perf_counter()
        factors = kernel_factors(axes, self.lengthscales, self.signal_variance)
        self.timings["fit_kernel_s"] = perf_counter() - t
        t = perf_counter()
        decompositions = [np.linalg.eigh(k) for k in factors]
        self.vectors = [d[1] for d in decompositions]
        denominator = np.multiply.outer(decompositions[0][0], decompositions[1][0])
        denominator += self.noise_variance
        if np.any(denominator <= 0):
            raise np.linalg.LinAlgError("Nonpositive noisy spectral eigenvalue")
        self.inverse_eigenvalues = 1.0 / denominator
        self.timings["fit_factor_s"] = perf_counter() - t
        t = perf_counter()
        qx, qy = self.vectors
        transformed_y = qx.T @ np.asarray(y).reshape(self.shape) @ qy
        self.alpha_hat = transformed_y * self.inverse_eigenvalues
        self.timings["fit_solve_s"] = perf_counter() - t
        self.state_bytes = int(sum(q.nbytes for q in self.vectors)
                               + self.alpha_hat.nbytes + self.inverse_eigenvalues.nbytes)
        return self

    def solve(self, rhs):
        qx, qy = self.vectors
        transformed = qx.T @ np.asarray(rhs).reshape(self.shape) @ qy
        return (qx @ (transformed * self.inverse_eigenvalues) @ qy.T).ravel()

    def predict(self, test_x, return_variance=True):
        t = perf_counter()
        cross = cross_factors(test_x, self.axes, self.lengthscales, self.signal_variance)
        tx = cross[0] @ self.vectors[0]
        ty = cross[1] @ self.vectors[1]
        self.timings["predict_cross_s"] = perf_counter() - t
        t = perf_counter()
        mean = np.einsum("qi,ij,qj->q", tx, self.alpha_hat, ty, optimize=True)
        self.timings["predict_mean_s"] = perf_counter() - t
        if not return_variance:
            return mean, None
        t = perf_counter()
        reduction = np.einsum("qi,ij,qj->q", tx * tx, self.inverse_eigenvalues,
                              ty * ty, optimize=True)
        variance = self.signal_variance - reduction
        self.min_raw_variance = float(variance.min())
        self.timings["predict_variance_s"] = perf_counter() - t
        return mean, np.maximum(variance, 0.0)
