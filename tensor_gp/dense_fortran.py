"""Hostile audit baseline: eliminate the original dense kernel's layout copy.

This is a separate, explicitly labeled baseline, not a post-hoc replacement of
preregistered DenseGP. It uses the SAME full dense Cholesky and predictions.
"""
from time import perf_counter
import numpy as np
from scipy.linalg import cho_factor, cho_solve
from .dense import DenseGP
from .kernels import kernel_factors


class DenseFortranGP(DenseGP):
    def fit(self, axes, y):
        if len(axes) != 2:
            raise ValueError("Two dimensional audit only")
        self.axes = axes
        t = perf_counter()
        kx, ky = kernel_factors(axes, self.lengthscales, self.signal_variance)
        nx, ny = len(axes[0]), len(axes[1])
        n = nx * ny
        covariance = np.empty((n, n), dtype=np.float64, order="F")
        # A view, not a reshape copy: flat C-grid indices have y fastest.
        view = covariance.reshape(ny, nx, ny, nx, order="F")
        assert np.shares_memory(view, covariance)
        np.multiply(ky[:, None, :, None], kx[None, :, None, :], out=view)
        covariance.flat[::n + 1] += self.noise_variance
        self.timings["fit_kernel_s"] = perf_counter() - t
        t = perf_counter()
        self.chol = cho_factor(covariance, lower=True, overwrite_a=True, check_finite=False)
        self.timings["fit_factor_s"] = perf_counter() - t
        t = perf_counter()
        self.alpha = cho_solve(self.chol, y, overwrite_b=False, check_finite=False)
        self.timings["fit_solve_s"] = perf_counter() - t
        self.state_bytes = int(self.chol[0].nbytes + self.alpha.nbytes)
        return self
