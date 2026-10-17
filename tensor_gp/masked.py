"""Exploratory missing-grid exact dense and tolerance-controlled PCG GPs."""
from __future__ import annotations
from time import perf_counter
import numpy as np
from scipy.linalg import cho_factor, cho_solve, solve_triangular
from scipy.sparse.linalg import LinearOperator, cg
from .kernels import cross_factors, kernel_factors
from .spectral import SpectralGP


def observed_subset(n, fraction, seed):
    if not 0 <= fraction < 1:
        raise ValueError("Missing fraction must be in [0,1)")
    m = max(1, round(n * (1 - fraction)))
    return np.sort(np.random.default_rng(20000 + seed).choice(n, m, replace=False))


class MaskedBase:
    def __init__(self, lengthscales=(0.18, 0.23), signal_variance=1.0, noise_variance=0.0025):
        self.lengthscales = tuple(lengthscales)
        self.signal_variance = signal_variance
        self.noise_variance = noise_variance
        self.timings = {}

    def _setup(self, axes, observed):
        self.axes = axes
        self.shape = (len(axes[0]), len(axes[1]))
        self.n = int(np.prod(self.shape))
        self.observed = np.asarray(observed)
        self.ix, self.iy = np.unravel_index(self.observed, self.shape)
        self.factors = kernel_factors(axes, self.lengthscales, self.signal_variance)

    def _cross(self, test_x):
        cx, cy = cross_factors(test_x, self.axes, self.lengthscales, self.signal_variance)
        return cx[:, self.ix] * cy[:, self.iy]


class DenseMaskedGP(MaskedBase):
    def fit(self, axes, observed, y):
        t = perf_counter()
        self._setup(axes, observed)
        m = len(observed)
        kx, ky = self.factors
        covariance = np.empty((m, m), dtype=np.float64, order="F")
        # Bounded temporaries; avoids materializing the unobserved full N×N grid.
        for start in range(0, m, 512):
            end = min(start + 512, m)
            covariance[:, start:end] = (kx[self.ix[:, None], self.ix[None, start:end]]
                                      * ky[self.iy[:, None], self.iy[None, start:end]])
        covariance.flat[::m + 1] += self.noise_variance
        self.timings["fit_kernel_s"] = perf_counter() - t
        t = perf_counter()
        self.chol = cho_factor(covariance, lower=True, overwrite_a=True, check_finite=False)
        self.timings["fit_factor_s"] = perf_counter() - t
        t = perf_counter()
        self.alpha = cho_solve(self.chol, y, check_finite=False)
        self.timings["fit_solve_s"] = perf_counter() - t
        self.state_bytes = self.chol[0].nbytes + self.alpha.nbytes
        return self

    def predict(self, test_x, return_variance=True):
        t = perf_counter()
        cross = self._cross(test_x)
        self.timings["predict_cross_s"] = perf_counter() - t
        t = perf_counter()
        mean = cross @ self.alpha
        self.timings["predict_mean_s"] = perf_counter() - t
        if not return_variance:
            return mean, None
        t = perf_counter()
        v = solve_triangular(self.chol[0], cross.T, lower=True, check_finite=False)
        variance = self.signal_variance - np.einsum("ij,ij->j", v, v)
        self.min_raw_variance = float(variance.min())
        self.timings["predict_variance_s"] = perf_counter() - t
        return mean, np.maximum(variance, 0.0)


class PCGMaskedGP(MaskedBase):
    def __init__(self, *args, rtol=1e-11, maxiter=2000, precondition=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.rtol = rtol
        self.maxiter = maxiter
        self.precondition = precondition
        self.iterations = []
        self.relative_residuals = []

    def _matvec(self, v):
        full = np.zeros(self.n)
        full[self.observed] = v
        kx, ky = self.factors
        result = (kx @ full.reshape(self.shape) @ ky.T).ravel()
        return result[self.observed] + self.noise_variance * v

    def _precondition(self, v):
        full = np.zeros(self.n)
        full[self.observed] = v
        return self.full_gp.solve(full)[self.observed]

    def _solve(self, rhs):
        iterations = 0
        def callback(_):
            nonlocal iterations
            iterations += 1
        solution, info = cg(self.operator, rhs, M=self.preconditioner, rtol=self.rtol,
                            atol=0.0, maxiter=self.maxiter, callback=callback)
        residual = np.linalg.norm(self._matvec(solution) - rhs) / max(np.linalg.norm(rhs), 1e-300)
        self.iterations.append(iterations)
        self.relative_residuals.append(float(residual))
        if info != 0:
            raise RuntimeError(f"CG failed: info={info}, iterations={iterations}, residual={residual}")
        return solution

    def fit(self, axes, observed, y):
        t = perf_counter()
        self._setup(axes, observed)
        m = len(observed)
        self.operator = LinearOperator((m, m), matvec=self._matvec, dtype=np.float64)
        self.timings["fit_kernel_s"] = perf_counter() - t
        t = perf_counter()
        self.preconditioner = None
        if self.precondition:
            self.full_gp = SpectralGP(lengthscales=self.lengthscales,
                                     signal_variance=self.signal_variance,
                                     noise_variance=self.noise_variance).fit(axes, np.zeros(self.n))
            self.preconditioner = LinearOperator((m, m), matvec=self._precondition, dtype=np.float64)
        self.timings["fit_factor_s"] = perf_counter() - t
        t = perf_counter()
        self.alpha = self._solve(y)
        self.timings["fit_solve_s"] = perf_counter() - t
        self.state_bytes = (sum(k.nbytes for k in self.factors) + self.observed.nbytes
                            + self.alpha.nbytes
                            + (self.full_gp.state_bytes if self.precondition else 0))
        return self

    def predict(self, test_x, return_variance=True):
        t = perf_counter()
        cross = self._cross(test_x)
        self.timings["predict_cross_s"] = perf_counter() - t
        t = perf_counter()
        mean = cross @ self.alpha
        self.timings["predict_mean_s"] = perf_counter() - t
        if not return_variance:
            return mean, None
        t = perf_counter()
        variance = np.empty(len(test_x))
        for i, k in enumerate(cross):
            variance[i] = self.signal_variance - k @ self._solve(k)
        self.min_raw_variance = float(variance.min())
        self.timings["predict_variance_s"] = perf_counter() - t
        return mean, np.maximum(variance, 0.0)
