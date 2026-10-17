# Mathematical derivation (calculated, not benchmark measurements)

## 1. The unchanged probabilistic model

Let training locations be every pair in X=X₁×X₂, with n₁, n₂ points and N=n₁n₂. Grid flattening is C-order: y-index varies fastest. Targets need not be separable. For the frozen squared-exponential kernel,

\[
k((x,y),(x',y'))=\sigma_f^2\exp[-(x-x')^2/(2\ell_1^2)]\exp[-(y-y')^2/(2\ell_2^2)].
\]

Put signal variance into the first factor, so K=K₁⊗K₂. The noisy training covariance is A=K+σₙ²I. The same training-only target mean is subtracted in both programs. Both condition on exactly the same training observations, fixed hyperparameters and isotropic observation noise. No hyperparameter optimizer is run or claimed to be accelerated.

Dense baseline computes Cholesky LLᵀ=A, α=A⁻¹y via triangular solves, μ*=K*α and latent variance v*=σ_f²−diag(K*A⁻¹K*ᵀ). It uses batched LAPACK solves, not A⁻¹ or Python loops.

## 2. Exact spectral solve

For the full, untruncated symmetric eigendecompositions Kᵢ=QᵢΛᵢQᵢᵀ,

\[
A=(Q_1\otimes Q_2)D(Q_1\otimes Q_2)^T,\quad
D_{ij}=\lambda_{1i}\lambda_{2j}+\sigma_n^2.
\]

Reshape centered targets to Y∈R^(n₁×n₂), set H=Q₁ᵀYQ₂, W=H⊘D. No N×N eigenvector matrix is formed. A full inverse-vector product, if needed for a residual or preconditioner, is vec(Q₁[(Q₁ᵀYQ₂)⊘D]Q₂ᵀ).

Off-grid test point r has cross-kernel row aᵣ⊗bᵣ. Let Uᵣ=aᵣQ₁, Vᵣ=bᵣQ₂. Then

\[
\mu_r=\sum_{ij}U_{ri}W_{ij}V_{rj}+\bar y,
\qquad
v_r=\sigma_f^2-\sum_{ij}U_{ri}^2D_{ij}^{-1}V_{rj}^2.
\]

These are exactly the same posterior mean and variance as dense conditioning in real arithmetic. Prediction does NOT require gridded test inputs. Implementation uses two matrix contractions, not a Q×N×N tensor. Both solvers clip negative raw variances to zero as numerical hygiene; the minimum raw variance is retained in every result, so clipping is auditable.

This identity is established prior work. See the source audit in `references.json`, especially `linear_operator`'s Kronecker-plus-constant-diagonal solve. Our contribution here is an independently implemented and measured CPU pipeline, explicit off-grid variance contraction, cold-start/layout audits and reproducible evidence, not a new theorem.

## 3. Complexity and leading arithmetic

Let M be the number of test points (512 in the primary case).

| Operation | Dense baseline | Tensor spectral |
|---|---|---|
| Kernel preparation | Θ(N²) multiply/store operations; same small per-axis exponentials | Θ(n₁²+n₂²) |
| Factorization | N³/3 leading Cholesky FLOPs | O(n₁³+n₂³) full eigensystems |
| Training solve | approximately 2N² | approximately 2N(n₁+n₂) for forward tensor transform; O(N) divisions |
| Cross-basis construction | O(MN), storing MN doubles | approximately 2M(n₁²+n₂²) FLOPs, storing M(n₁+n₂) doubles |
| Predictive mean | approximately 2MN | approximately 2MN plus O(Mn₂) |
| Predictive variance | approximately MN² | approximately 2MN plus O(M(n₁+n₂)) |
| Principal learned arrays | 8N²+8N bytes | 8(n₁²+n₂²+2N) bytes |

For n₁=128,n₂=64,N=8192,M=512:

* Dense Cholesky: **183,251,937,963** leading FLOPs (N³/3).
* Dense triangular variance solve: **34,359,738,368** leading FLOPs (MN²).
* Tensor training transform: **3,145,728** FLOPs.
* Tensor cross-basis transformations: **20,971,520** FLOPs.
* Each of the mean and variance matrix contractions: approximately **8,388,608** FLOPs, plus small reductions.
* Full eigensolver constants are algorithm-dependent. Do not equate n₁³+n₂³=2,359,296 with exact eigensolver FLOPs. Assuming, only illustratively, a coefficient of ten would add about 23.6 million FLOPs. The leading arithmetic reduction is then several thousandfold, **not a measured wall-clock speedup**.
* Dense model-array storage: **536,936,448 bytes**. Tensor arrays: **294,912 bytes**. These omit axes, Python objects, temporary allocations, input/output and libraries; measured process peak RSS is a different metric.

Dense construction and Cholesky are memory-intensive: at least 8N² bytes must be written and factorized, and a row/column layout copy can add another full matrix read+write. A bandwidth lower bound is transferred_bytes / sustainable_bytes_per_second; sustainable bandwidth is not assumed equal to hardware nameplate. The hostile Fortran audit removes the extra full dense layout copy and reports whether the overall claim survives.

## 4. Amdahl, startup and the correct claim

For baseline total T_b=T_common+T_fit+T_pred, if only one component of fraction f is accelerated g times,

\[
S=\frac{1}{(1-f)+f/g}.
\]

The implementation accelerates both fitting and predictive variance, not just Cholesky. Cold interpreter/import and input/output costs remain. Even infinite compute speed cannot exceed T_b/T_common. Derive actual f and the cap from raw per-stage measurements; component or in-process gains must not replace the primary full-process ratio.

The primary estimator is ΣT_dense / ΣT_spectral across ALL 15 matched cold subprocess pairs. This is not the mean of cherry-picked pair ratios. The 95% interval resamples the FIVE dataset-seed clusters with their three repetitions intact (10,000 resamples). It is a modest descriptive interval on this sandbox, not a hardware-independent guarantee or a measurement of cold filesystem caches.

## 5. Floating point and quality

In exact arithmetic there is no approximation error because the covariance, noisy eigenspectrum and complete basis are unchanged. IEEE float64 arithmetic differs between Cholesky and eigendecomposition. A conservative bound is κ₂(A)≤(Nσ_f²+σₙ²)/σₙ², approximately 3.28×10⁶ at primary settings, so conditioning matters despite algebraic equivalence. For a perturbation E with ||A⁻¹E||<1, the standard inverse perturbation bound is

\[
\frac{\|\delta\alpha\|}{\|\alpha\|}\lesssim
\frac{\kappa(A)\,\|E\|/\|A\|}{1-\kappa(A)\,\|E\|/\|A\|}.
\]

This is a conditioning explanation, NOT proof that every floating-point setting satisfies the empirical tolerance. Report observed residuals, nonpositive spectral denominators, raw negative variances and failures at near-zero noise. The preregistered primary held-out RMSE allowance is 1e−7 absolute; max-mean, max-variance and predictive-NLL agreement each have separate 1e−6 guardrails. These criteria are not loosened after seeing data. Testing uses continuous independently sampled test inputs and an independent noise stream, not training points.

## 6. Missing-grid extension and why it is separate

With selection matrix S keeping m observed grid locations, A_obs=SKSᵀ+σₙ²I_m. A matvec scatters a vector to the full grid, applies K₁ Z K₂ᵀ, gathers observations and adds noise. Cost is O(N(n₁+n₂)) without an m×m kernel. Conjugate gradients use this operator. A candidate SPD preconditioner is P=S(K+σₙ²I_N)⁻¹Sᵀ, applying the exact full-grid inverse to a zero-filled vector.

For no missing values, P is exact; for missing values it is NOT the observed inverse. Iteration count can deteriorate, and each posterior-variance query needs another solve. A fast training/mean-only solve does not establish a fast full mean+variance GP. Extension timings, convergence and failures must therefore be separate from the primary complete-grid experiment. No result for heteroscedastic noise, arbitrary nonseparable kernels, arbitrary off-grid training inputs or arbitrary neural networks follows from the main identity.
