"""Exact tensor marginal likelihood and gradients; same probabilistic GP.

No eigenvector differentiation is needed: use 1/2 trace((aa^T-A^-1)dA).
This is a known GP gradient identity, specialized to the Kronecker basis.
"""
from __future__ import annotations
import numpy as np
from scipy.linalg import eigh
from scipy.optimize import minimize
from .kernels import kernel_factors
from .spectral import SpectralGP


class TensorObjective:
    def __init__(self, axes, centered_y):
        self.axes = axes
        self.shape = tuple(len(a) for a in axes)
        self.y = np.asarray(centered_y).reshape(self.shape)
        self.n = self.y.size

    def __call__(self, theta):
        signal, ellx, elly, noise = np.exp(theta)
        kx, ky = kernel_factors(self.axes, (ellx, elly), signal)
        lx, qx = eigh(kx, check_finite=False, driver="evd")
        ly, qy = eigh(ky, check_finite=False, driver="evd")
        products = lx[:, None] * ly[None, :]
        denom = products + noise
        if np.any(denom <= 0):
            raise np.linalg.LinAlgError("Nonpositive noisy covariance eigenvalue")
        inv = 1.0 / denom
        h = qx.T @ self.y @ qy
        w = h * inv
        nll = 0.5 * (np.sum(h * w) + np.sum(np.log(denom)) + self.n * np.log(2 * np.pi))
        dx = (self.axes[0][:, None] - self.axes[0][None, :]) / ellx
        dy = (self.axes[1][:, None] - self.axes[1][None, :]) / elly
        gx = qx.T @ (kx * dx**2) @ qx
        gy = qy.T @ (ky * dy**2) @ qy
        grad = np.empty(4)
        grad[0] = 0.5 * np.sum((w*w - inv) * products)
        grad[1] = 0.5 * (np.sum(w * (gx @ w) * ly[None, :])
                         - np.sum(inv * np.diag(gx)[:, None] * ly[None, :]))
        grad[2] = 0.5 * (np.sum(w * (w @ gy) * lx[:, None])
                         - np.sum(inv * lx[:, None] * np.diag(gy)[None, :]))
        grad[3] = 0.5 * noise * (np.sum(w*w) - np.sum(inv))
        return float(nll), -grad


def optimizer_options(spec):
    return {k: v for k, v in spec["optimizer"].items() if k != "method"}


def record_optimizer_call(history, theta, value, gradient):
    history.append({"theta": np.asarray(theta).tolist(), "negative_lml": float(value),
                    "gradient_inf_norm": float(np.max(np.abs(gradient)))})


class TensorHyperGP:
    def __init__(self, spec):
        self.spec = spec
        self.history = []

    def fit(self, axes, y):
        objective = TensorObjective(axes, y)
        def fun(theta):
            value, gradient = objective(theta)
            record_optimizer_call(self.history, theta, value, gradient)
            return value, gradient
        initial = np.log([1.0, 0.18, 0.23, 0.0025])
        bounds = np.log(np.asarray(self.spec["bounds_untransformed"]))
        self.optimization = minimize(fun, initial, method="L-BFGS-B", jac=True,
                                     bounds=bounds, options=optimizer_options(self.spec))
        self.theta = self.optimization.x.copy()
        signal, ellx, elly, self.noise_variance = np.exp(self.theta)
        self.model = SpectralGP(lengthscales=(ellx, elly), signal_variance=signal,
                                noise_variance=self.noise_variance).fit(axes, y)
        self.state_bytes = self.model.state_bytes
        return self

    def predict(self, test_x):
        mean, var = self.model.predict(test_x)
        self.min_raw_variance = self.model.min_raw_variance
        return mean, var


class SklearnHyperGP:
    def __init__(self, spec):
        self.spec = spec
        self.history = []

    def fit(self, axes, y):
        # Import is charged in the complete cold-process pipeline.
        from sklearn.gaussian_process import GaussianProcessRegressor
        from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel
        b = self.spec["bounds_untransformed"]
        kernel = (ConstantKernel(1.0, tuple(b[0]))
                  * RBF([0.18, 0.23], np.array(b[1:3]))
                  + WhiteKernel(0.0025, tuple(b[3])))
        def optimizer(obj_func, initial_theta, bounds):
            def fun(theta):
                value, gradient = obj_func(theta, eval_gradient=True)
                record_optimizer_call(self.history, theta, value, gradient)
                return value, gradient
            self.optimization = minimize(fun, initial_theta, method="L-BFGS-B", jac=True,
                                         bounds=bounds, options=optimizer_options(self.spec))
            return self.optimization.x, self.optimization.fun
        grid = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 2)
        self.model = GaussianProcessRegressor(kernel=kernel, alpha=0.0, optimizer=optimizer,
                                               normalize_y=False, n_restarts_optimizer=0)
        self.model.fit(grid, y)
        self.theta = self.model.kernel_.theta.copy()
        self.noise_variance = float(np.exp(self.theta[3]))
        self.state_bytes = self.model.L_.nbytes + self.model.alpha_.nbytes
        return self

    def predict(self, test_x):
        mean, observed_std = self.model.predict(test_x, return_std=True)
        var = observed_std**2 - self.noise_variance
        self.min_raw_variance = float(var.min())
        return mean, np.maximum(var, 0.0)
