"""Frozen strong baseline: exact dense GP using LAPACK, not explicit inverse."""
from __future__ import annotations

from time import perf_counter

import numpy as np
from scipy.linalg import cho_factor, cho_solve, solve_triangular

from .kernels import cross_factors, kernel_factors, row_tensor_product


class DenseGP:
    def __init__(self, lengthscales=(0.18, 0.23), signal_variance=1.0, noise_variance=0.0025):
        self.lengthscales = tuple(lengthscales)
        self.signal_variance = float(signal_variance)
        self.noise_variance = float(noise_variance)
        self.timings = {}

    def fit(self, axes, y):
        self.axes = axes
        t = perf_counter()
        factors = kernel_factors(axes, self.lengthscales, self.signal_variance)
        covariance = factors[0]
        for factor in factors[1:]:
            covariance = np.kron(covariance, factor)
        covariance = np.asarray(covariance, order="F")
        covariance.flat[::covariance.shape[0] + 1] += self.noise_variance
        self.timings["fit_kernel_s"] = perf_counter() - t
        t = perf_counter()
        self.chol = cho_factor(covariance, lower=True, overwrite_a=True, check_finite=False)
        self.timings["fit_factor_s"] = perf_counter() - t
        t = perf_counter()
        self.alpha = cho_solve(self.chol, y, overwrite_b=False, check_finite=False)
        self.timings["fit_solve_s"] = perf_counter() - t
        self.state_bytes = int(self.chol[0].nbytes + self.alpha.nbytes)
        return self

    def predict(self, test_x, return_variance=True):
        t = perf_counter()
        cross = row_tensor_product(cross_factors(test_x, self.axes, self.lengthscales,
                                                 self.signal_variance))
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
        variance = np.maximum(variance, 0.0)
        self.timings["predict_variance_s"] = perf_counter() - t
        return mean, variance
