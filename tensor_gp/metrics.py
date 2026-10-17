"""Held-out quality metrics; tolerance lives only in preregister.json."""
import numpy as np


def quality_metrics(mean, latent_variance, test_y, test_latent, noise_variance):
    if not (np.isfinite(mean).all() and np.isfinite(latent_variance).all()):
        raise ValueError("Nonfinite posterior prediction")
    observed_variance = latent_variance + noise_variance
    if np.any(observed_variance <= 0):
        raise ValueError("Nonpositive predictive variance")
    residual = test_y - mean
    return {
        "rmse": float(np.sqrt(np.mean(residual**2))),
        "latent_rmse": float(np.sqrt(np.mean((test_latent - mean)**2))),
        "nll": float(0.5 * np.mean(np.log(2 * np.pi * observed_variance)
                                   + residual**2 / observed_variance)),
        "coverage_95": float(np.mean(np.abs(residual) <= 1.959963984540054 * np.sqrt(observed_variance))),
        "min_latent_variance": float(np.min(latent_variance)),
        "max_latent_variance": float(np.max(latent_variance)),
    }
