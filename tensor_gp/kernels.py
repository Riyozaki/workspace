"""Identical kernel arithmetic shared by both solvers."""
from __future__ import annotations

import numpy as np


def rbf_1d(a: np.ndarray, b: np.ndarray, lengthscale: float) -> np.ndarray:
    delta = (np.asarray(a, dtype=np.float64)[:, None]
             - np.asarray(b, dtype=np.float64)[None, :]) / lengthscale
    return np.exp(-0.5 * delta * delta)


def kernel_factors(axes, lengthscales, signal_variance=1.0):
    factors = [rbf_1d(a, a, ell) for a, ell in zip(axes, lengthscales, strict=True)]
    factors[0] *= signal_variance
    return factors


def cross_factors(test_x, axes, lengthscales, signal_variance=1.0):
    factors = [rbf_1d(test_x[:, i], axis, ell)
               for i, (axis, ell) in enumerate(zip(axes, lengthscales, strict=True))]
    factors[0] *= signal_variance
    return factors


def row_tensor_product(factors):
    """Rows have the same C-order tensor indexing as training targets."""
    out = factors[0]
    for factor in factors[1:]:
        out = (out[:, :, None] * factor[:, None, :]).reshape(out.shape[0], -1)
    return out
