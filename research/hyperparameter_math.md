# Exact GP hyperparameter learning without the dense N×N precision matrix

This is an extension of the same established Kronecker method, not a different
training objective. All quantities below are **DERIVED**, not wall-clock results.

Let θ = log(signal variance, lengthscale x, lengthscale y, noise variance),
A(θ)=K₁(θ)⊗K₂(θ)+σₙ²I, H=Q₁ᵀYQ₂ and Dᵢⱼ=λ₁ᵢλ₂ⱼ+σₙ².
The identical negative log marginal likelihood minimized by both programs is

\[
J(\theta)=\tfrac12 y^TA^{-1}y+\tfrac12\log\det A+\tfrac N2\log(2\pi)
=\tfrac12\sum_{ij}H_{ij}^2/D_{ij}+\tfrac12\sum_{ij}\log D_{ij}+\tfrac N2\log(2\pi).
\]

Write W=H/D and R=1/D. The standard GP gradient identity is

\[
\partial J/\partial\theta_p=\tfrac12\operatorname{tr}[(A^{-1}-\alpha\alpha^T)\partial A/\partial\theta_p].
\]

We do not differentiate eigenvectors. For a parameter in K₁, form
B₁=Q₁ᵀ(∂K₁/∂θ)Q₁. The trace and quadratic terms become

\[
\operatorname{tr}(A^{-1}\partial A)=\sum_{ij}R_{ij}(B_1)_{ii}\lambda_{2j},
\quad
\alpha^T(\partial A)\alpha=\sum_j\lambda_{2j} W_{:j}^TB_1W_{:j}.
\]

For a parameter in K₂ the analogous terms are
Σᵢⱼ Rᵢⱼ λ₁ᵢ (B₂)ⱼⱼ and Σᵢ λ₁ᵢ Wᵢ: B₂ Wᵢ:ᵀ.
For log signal variance, B₁=Λ₁, and

\[
\partial J/\partial\log\sigma_f^2=\tfrac12\sum_{ij}(R_{ij}-W_{ij}^2)\lambda_{1i}\lambda_{2j}.
\]

For log noise variance,

\[
\partial J/\partial\log\sigma_n^2=\tfrac12\sigma_n^2(\sum R_{ij}-\sum W_{ij}^2).
\]

The RBF lengthscale derivative is ∂Kᵢ/∂log ℓᵢ = Kᵢ ⊙ ((x−x′)/ℓᵢ)².
No approximate log determinant, stochastic trace estimator, rank truncation,
early exit based on held-out labels or different kernel is used.

## Complexity

Each objective/gradient evaluation costs O(n₁³+n₂³+N(n₁+n₂)) and
O(n₁²+n₂²+N) working arrays, for a fixed number of kernel parameters.
The standard dense sklearn GP computes a Cholesky and the exact dense GP
hypergradient (including a precision-matrix solve) with cubic arithmetic and
quadratic arrays per evaluation. Its code is the library's own implementation,
not a deliberately unoptimized Python baseline.

## Optimization fairness

Both programs use the same SciPy L-BFGS-B implementation, initial log parameters,
bounds, maxiter, maxfun, maxls, ftol and gtol, fixed in
`hyperparameter_protocol.json` before objective evaluation. All evaluations,
including rejected line searches, are timed and logged. The final posterior is
refit and mean+latent variance is evaluated at every held-out point. sklearn's
WhiteKernel predictive observation variance is converted to latent variance by
subtracting its learned noise variance; the same noise is then used in NLL.

Floating-point perturbations can change line-search paths, so identical iteration
counts are checked rather than assumed. Optimizer convergence flags, warnings,
objective differences, parameter differences, all evaluation counts, quality
failures and timeouts must remain in the report. A faster but worse converged
solution is not considered lossless.
