# Research work log

All timestamps are tool-observed UTC. The 90-minute budget is 5,400 seconds measured against `research/start_time.json`. No elapsed time is fabricated.

## Stage 1 — environment and brainstorm

- Tool time: 2026-10-17T13:58:35.712731+00:00; elapsed: 0 seconds.
- Starting environment inspection, at least eight hypotheses, and metric preregistration.

- Environment checkpoint: 2026-10-17T13:59:38.321480+00:00; elapsed 62.608 s. CPU-only: 2 logical CPUs, approximately 4 GiB RAM.

## Preregistration frozen

- Tool time: 2026-10-17T14:01:08.590169+00:00; elapsed 152.877 s (within first 600 s).
- SHA-256: `4c9c3843843737bfd6c790f4e47226a7b81d6323464fc01454f24e397179eba5`. Baseline, primary size, all five seeds, 15 paired runs, full cold-process timing, RMSE tolerance 1e-7 and mean/variance/NLL guardrails fixed before any model measurement.
- See `research/brainstorm.md` for ten ideas, estimates, risks and the two selected algorithms.
- Primary task: exact GP regression on a declared 128×64 Cartesian grid, 512 independent held-out test points, float64, two BLAS threads. Synthetic structural benchmark; no universal AI-acceleration claim.
- No optimized solver has been implemented or run.

## Stage 2 — selection and baseline measurement

- Tool time: 2026-10-17T14:02:57.346452+00:00; elapsed 261.633 s; remaining 5138.367 s.
- Selected exact spectral Kronecker GP and a separately labeled masked-PCG extension. Starting frozen dense baseline before implementing either optimization; full-size initial baseline, all five seeds.

## Baseline running — source and methodological audit

- Tool time: 2026-10-17T14:03:50.909873+00:00; elapsed 315.197 s; remaining 5084.803 s.
- Reviewing optimized scikit-learn GP prediction and established Kronecker-plus-diagonal implementations; no optimized solver implemented yet.

### Baseline completed before optimization

- Tool time: 2026-10-17T14:04:53.218266+00:00; elapsed 377.505 s.
- All five full-size dense runs succeeded. Cold walls: [3.995934367000018, 3.8165294159999803, 3.71976474600001, 3.6420116209999946, 3.6955255100000386] s. All raw runs retained under `results/runs/baseline_initial/`.
- Baseline source hashes saved before measurement. Exact structured solver still absent.
- Source audit confirms scikit-learn uses Cholesky plus batched triangular posterior-variance solve, as this baseline does. Existing linear_operator library already implements Kronecker-plus-diagonal structure: no novelty claim.

## Stage 3 — exact structured solver implementation

- Tool time: 2026-10-17T14:05:22.825548+00:00; elapsed 407.113 s; remaining 4992.887 s.
- Initial baseline completed and saved before optimization. Implementing full-rank per-axis eigendecomposition and exact off-grid mean AND variance. No truncation, no retraining, no changed noise or metric.

## Stage 4 — preregistered end-to-end paired experiment

- Tool time: 2026-10-17T14:07:30.405686+00:00; elapsed 534.693 s; remaining 4865.307 s.
- 33 unit/reference tests passed. Primary implementation unchanged since these tests. Starting all 15 predeclared pairs, randomized and balanced method order, isolated processes, two threads, includes startup/import/input/output and posterior variance. Every attempt retained; report tolerances unchanged.

## Stage 5 — hostile baseline and end-to-end audit

- Tool time: 2026-10-17T14:09:09.596313+00:00; elapsed 633.883 s; remaining 4766.117 s.
- Primary frozen experiment: 15 pairs, 11.5406x cold speedup, 95% seed-cluster bootstrap [10.2796,12.8830], all quality guardrails pass. Individual pairs range 9.1487–15.6884x; not every run exceeds 10x. Now testing a stronger one-pass-Fortran dense covariance baseline and import/startup sensitivity. Neither replaces the preregistered baseline or primary results.

## Stage 5A — four-way audit begins

- Tool time: 2026-10-17T14:11:18.757550+00:00; elapsed 763.045 s; remaining 4636.955 s.
- 43 tests passed, including bitwise-identical Cholesky factors for original vs one-pass Fortran covariance. Four variants: frozen dense, better-layout dense, original spectral, NumPy-only spectral. Same data and locked quality criteria; all 15 repeats per variant retained. Import optimization is a separate new method variant, not a rewrite of primary measurements.

## Stage 5B — mathematical derivation and measurement critique

- Tool time: 2026-10-17T14:12:08.815411+00:00; elapsed 813.102 s; remaining 4586.898 s.
- While isolated audit workers run, deriving the complete mean+variance algorithm and Amdahl limits; no concurrent numerical benchmark or training process. Main concern: dense array layout costs and numerical-library startup could explain some of the initial headline.

## Stage 5C — hostile audit interpretation and scale tests

- Tool time: 2026-10-17T14:13:38.224124+00:00; elapsed 902.511 s; remaining 4497.489 s.
- Four-way audit completed: NumPy-only method 30.33x versus stronger one-pass-Fortran dense baseline on 15 pairs, all locked quality guardrails pass. Original spectral pipeline remains separately reported. Original preregistered 11.54x is not replaced. Beginning small/large-size scaling to expose where startup prevents 10x.

## Stage 6 — missing-grid extension design (exploratory)

- Tool time: 2026-10-17T14:14:48.745371+00:00; elapsed 973.032 s; remaining 4426.968 s.
- Designing matrix-free PCG with full-grid spectral preconditioning, same RMSE/mean/variance/NLL criteria, all mean+variance solve costs included. Missingness and iteration tolerances will be frozen before extension measurements. This is not part of the primary 15 pairs and may be slower or fail.

## Stage 5D — challenge dense diagonal-update implementation

- Tool time: 2026-10-17T14:17:15.139585+00:00; elapsed 1119.427 s; remaining 4280.573 s.
- Scaling complete. Investigating why even one-pass dense kernel construction takes >1 s; suspect NumPy flat slicing on Fortran arrays. This component diagnostic is NOT a system speedup and will be followed by a complete remeasurement if a stronger dense path is found.

## Stage 6A — missing-grid pilot validation

- Tool time: 2026-10-17T14:18:57.793170+00:00; elapsed 1222.080 s; remaining 4177.920 s.
- Diagonal-update suspicion was NOT confirmed: flat vs index vs explicit-stride updates were all sub-millisecond for N=8192, not the ~1 s construction cost. Negative diagnostic retained. Running small missing-grid correctness tests before full extension benchmarks.

## Stage 6B — full missing-grid mean-and-variance experiments

- Tool time: 2026-10-17T14:19:37.038400+00:00; elapsed 1261.325 s; remaining 4138.675 s.
- 52 tests passed, including independently validated sklearn, dense and PCG missing-grid posteriors. Running pilot plus all 20 predeclared full-grid masks, 512 variance solves per full PCG run, 180 s timeout per method. Timeouts/failures are retained, not discarded. No other numerical workload will run concurrently.

## Stage 6C — measurement bug found and invalidated

- Tool time: 2026-10-17T14:20:18.355770+00:00; elapsed 1302.643 s; remaining 4097.357 s.
- Detected extension-only filename collision: Path.with_suffix treated decimal missing fractions in run IDs as file suffixes, so dense and PCG prediction artifacts could overwrite each other. Stopped extension immediately. The initial masked comparison guards are INVALID and will not support any claim. Primary/four-way/scaling IDs have no dots and use distinct files, so they are unaffected; will re-audit hashes. Keeping invalid runs and rerunning with a new label after a regression fix. No metric/tolerance change.

## Stage 6D — artifact isolation fixed; primary independently revalidated

- Tool time: 2026-10-17T14:21:30.830367+00:00; elapsed 1375.117 s; remaining 4024.883 s.
- 56 tests pass. Output extensions now append instead of replacing decimals; harness rejects shared or overwritten prediction paths and records per-run SHA-256. All 15 original primary pairs were recomputed from their 30 distinct artifacts, with matching RMSE; unchanged. Initial masked artifacts explicitly invalidated and retained. Restarting unchanged masked protocol under a new experiment label.

## Stage 7 — exact hyperparameter-training extension design

- Tool time: 2026-10-17T14:22:29.059786+00:00; elapsed 1433.347 s; remaining 3966.653 s.
- Preparing a further use of the same exact tensor identity: log marginal likelihood and analytic gradients for GP hyperparameter optimization, against standard scikit-learn GPR with identical L-BFGS-B settings. This is a separately preregistered exploratory study, not a change to the primary fixed-hyperparameter baseline. Only code/documentation now; no numerical workloads concurrent with the masked study.

## Stage 7A — hyperparameter objective code ready, not yet measured

- Tool time: 2026-10-17T14:28:05.656640+00:00; elapsed 1769.944 s; remaining 3630.056 s.
- Training extension protocol and analytic-gradient implementation written and hashed before objective evaluations. Will run independent gradient/optimizer tests only after the active masked study exits, to avoid timing interference. Fixed initial hyperparameters and L-BFGS-B bounds/settings; all test metrics remain locked.

## Stage 8 — reproducibility and report scaffolding

- Tool time: 2026-10-17T14:29:07.191946+00:00; elapsed 1831.479 s; remaining 3568.521 s.
- Preparing a one-command fresh-output reproduction runner and documentation while the only active numerical workload remains the masked audit. Early valid masked cases are slower, not faster; their complete variance-solve cost is being retained. No final report is being submitted before minute 90.

## Stage 9 — independent natural-image validation design

- Tool time: 2026-10-17T14:36:04.277078+00:00; elapsed 2248.564 s; remaining 3151.436 s.
- Primary synthetic case is intentionally structural and cannot establish generality. To challenge target/data dependence, predeclaring all available Set12 benchmark images (not selecting by performance), five noise/test seeds and three timing repeats per image. Same frozen kernel and quality tolerances; disjoint held-out pixels, no train-pixel testing. Will keep this external structural-use-case evidence separate, not retroactively change the primary data.

## Stage 7B — hyperparameter gradient and optimizer verification

- Tool time: 2026-10-17T14:37:33.927515+00:00; elapsed 2338.214 s; remaining 3061.786 s.
- Corrected masked study finished all 23 planned pairs: quality passed but every nonzero full-grid missingness case is a major slowdown. No timeout/omitted full case. Numerical resources now free; testing exact tensor marginal-likelihood gradients and optimizer agreement against sklearn before training-extension timing.

## Stage 7C — full hyperparameter-training experiment

- Tool time: 2026-10-17T14:37:42.434377+00:00; elapsed 2346.721 s; remaining 3053.279 s.
- 69 tests passed including independent analytic-gradient/finite-difference checks and optimizer equivalence. One sklearn boundary ConvergenceWarning retained, not suppressed or tuned away. Starting all predeclared pilot + 10 full pairs (5 seeds x 2 repeats), including optimizer and every rejected line-search evaluation.

## Stage 8A — reproduction runner and independent corpus ready

- Tool time: 2026-10-17T14:48:05.432330+00:00; elapsed 2969.719 s; remaining 2430.281 s.
- One-command reproduction runner implemented, pinned Set12 corpus downloaded in full (12/12) before external quality evaluation. External timing will include PNG decoding and sampling, not only preprocessed matrices. Hyperparameter training remains the only timed numerical workload; three completed full pairs already have identical optimizer evaluation counts and quality, but no final aggregate is claimed before all pairs finish.

## Stage 7D — hyperparameter study complete; external setup

- Tool time: 2026-10-17T14:56:32.790265+00:00; elapsed 3477.077 s; remaining 1922.923 s.
- All pilot + 10 full learned-hyperparameter pairs completed. Same L-BFGS-B evaluation and iteration counts in each pair; all locked quality guardrails pass and optimizers converged. Will report this separately from primary. Installing PNG decoder for predeclared external corpus, outside timed measurements.

## Stage 9A — all-image external full-pipeline validation

- Tool time: 2026-10-17T14:56:48.261851+00:00; elapsed 3492.549 s; remaining 1907.451 s.
- 71 tests passed (one documented small-grid sklearn boundary warning). Hyperparameter full study: 276.7793x, 95% seed-cluster CI [258.0355,302.3639], 10/10 quality pass; separate exploratory result, not new primary. Starting all 180 Set12 pairs (12 images x 5 seeds x 3 timing repeats), actual PNG decode/sampling/input-to-output included; disjoint test pixels verified and provenance hashed.

## Stage 8B — reproducibility and evidence audit preparation

- Tool time: 2026-10-17T14:58:53.832588+00:00; elapsed 3618.120 s; remaining 1781.880 s.
- Added immutable-source, artifact hash, thread-limit and all-primary-pair rechecks; primary predictions will be exported as small CSV evidence. Full reproduction includes conditioning failures rather than suppressing them. No extra numerical benchmark runs concurrently with the active all-image study.

## Stage 10 — numerical conditioning stress tests

- Tool time: 2026-10-17T15:08:59.118060+00:00; elapsed 4223.405 s; remaining 1176.595 s.
- All 180 external pairs completed on all 12 Set12 images; no failed/omitted pairs and all locked quality guards pass. Starting the frozen 54-case noise/lengthscale stress plan, deliberately including near-singular cases; failures and loss of equivalence will be reported, with no adaptive jitter or tolerance changes.

## Stage 11 — verify the documented one-command reproduction

- Tool time: 2026-10-17T15:13:52.234135+00:00; elapsed 4516.521 s; remaining 883.479 s.
- All 54 conditioning stress cases completed. Some near-singular settings fail Cholesky/eigenspectrum checks or the original NLL/mean agreement guards; these failures remain in CSV and are not called lossless speedups. Now running exactly the documented bash reproduce.sh entrypoint in a fresh output directory, with tests plus primary and four-way audit, not overwriting original results.

## Stage 12 — evidence consistency and final documentation

- Tool time: 2026-10-17T15:17:40.482736+00:00; elapsed 4744.770 s; remaining 655.230 s.
- Documented one-command entrypoint completed successfully in a fresh directory (exit 0), tests + all primary pairs + four-way audit; original results untouched. Now checking every original artifact/thread limit and recomputing all 15 primary pairs/CI, exporting held-out predictions. Final report remains explicitly provisional until both clocks reach 5400 seconds.

## Stage 12A — late independent-seed stability and final residual audit

- Tool time: 2026-10-17T15:20:46.341353+00:00; elapsed 4930.628 s; remaining 469.372 s.
- Full report draft now includes all 180 external pairs, 54 conditioning cases and every failed/invalidated experiment. One-command reproduction passed 72 tests (one disclosed sklearn boundary warning). Beginning predeclared seeds 100..399, only a time-limited prefix, no quality selection; not pooled into primary. Remaining seconds before 5400 are used for random-RHS residual checks, not sleeping or fabricating time. Final publication is programmatically blocked until both real clocks reach 90 minutes.

## Stage 13 — final report gate after 90 real minutes

- Tool time: 2026-10-17T15:29:46.240301+00:00; elapsed 5470.527 s; remaining 0.000 s.
- Wall and monotonic clocks both reached 5400 s. Final report may now be published; no elapsed time was fabricated.

### Explicit timing deviation disclosure

- Tool-observed UTC: 2026-10-17T15:30:41.015069+00:00; elapsed 5525.302085 s. Numerical workload ended at 5400.000090 s; final gate was at 5470.527269 s.
- Strict total 90-minute budget including post-window integrity checks/document publication was exceeded. This is explicitly disclosed, not relabeled as exactly 90 minutes. No new ML benchmark was run after the deadline.
