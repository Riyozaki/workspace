# Frozen local protocol — 50× goal, no fictitious organizer score

## Scope fixed before results

This is a **new** real ML classification experiment: **pre-trained RBF-SVM inference on Fashion-MNIST**, all 28×28 grayscale pixels, 10 classes. No Cartesian/separable covariance assumption, no custom data generation/duplication, no inference on training examples. Old GP results contribute no credit. There is **no external frozen evaluator, unknown organizer holdout, or official leaderboard score**. Our local evaluator and a self-sequestered public holdout are not equivalent to independent verification.

The choice of inference is explicit: one shared SVC is trained once; subsequent full inference requests load a model, load/decode raw compressed input data, normalize pixels, predict all requested labels, postprocess, and write predictions/metadata. **Training is not part of this inference-only task.** Never describe a speedup of this request as speeding up training+inference. Report common training/export costs and a non-amortized calculation separately. Optimized model parameters may be exported once without data-dependent prediction caches; export time/bytes are separately recorded.

## Data / splits / model

- Dataset: **all** 60,000 official training examples and 10,000 official test examples from `zalandoresearch/fashion-mnist`, pinned Git commit in `source_commit.json` (`b2617bb6d3ffa2e429640350f613e3291e10b141`). Download exact four IDX.gz blobs via GitHub API; record Git blob SHA and SHA-256.
- Train: official 60,000, without subsampling. Validation / holdout: stratified halves of official test using `train_test_split(test_size=0.5, stratify=y_test, random_state=20261017)`. Thus 500 validation and 500 holdout observations per class, 5,000 each. Only validation results can influence implementation choice.
- Input transform: flatten in original row-major order, cast to float64, divide by 255. No learned target transforms, feature selection or augmentation.
- Shared model: scikit-learn `SVC(C=10.0, kernel='rbf', gamma='scale', shrinking=True, probability=False, tol=0.001, cache_size=1536, max_iter=-1, decision_function_shape='ovo', break_ties=False, random_state=20261017)`. No training hyperparameter search. C=10 is deliberately stronger than leaving C at its smaller default; not a claim of globally tuned SOTA. Save trained checkpoint and checksums. Keep every support vector.

## Strong baseline (selection rule frozen before baseline and custom optimization)

References, all predicting the **same trained model**:
1. native scikit-learn/libsvm `predict`;
2. same public API, two `ThreadPoolExecutor` chunks (no retraining, no model copies);
3. ONNX Runtime CPU `SVMClassifier`, exported using installed skl2onnx, intra-op threads=2, inter-op=1, graph optimization enabled; installation/export failure is recorded, not replaced with fabricated timing.

**Before writing/running custom optimized predictor**, run each available reference **3 fresh processes on validation** in a fixed shuffled order (seed=20261017). Eligible references must agree with native labels on >=99.9% and have accuracy >= native accuracy−0.001. Choose reference with smallest **mean full cold wall time across all 3 runs**, store `baseline_selected.json`, and never change it after optimized results. This predeclared baseline-configuration selection makes the reference stronger, not weaker; do not choose the fastest individual run. Report every reference, including failures. This exact selection rule, rather than a post-hoc preferred implementation, is the frozen baseline definition.

## Quality (unchangeable)

Primary metric: classification accuracy. Tolerance: method accuracy must be **at least baseline accuracy−0.001 absolute** (0.1 percentage point). Additional gate: **label agreement >=0.999**, same 5,000 ordered held-out examples, valid finite labels 0..9. Frozen `eval.py` implements both. No different loss/metric/steps/tolerance after results. Do not open or score holdout labels before final candidate/code freeze. Final quality claim is **local holdout only**, never an organizer-certified hidden-data claim.

## Candidate selection and complete timing

At most three systems: float64 batched kernel-GEMM; float32 kernel GEMM with float64 decisions; inference-only compact/NumPy checkpoint loading combined with the best validated arithmetic. Predeclared block choices 128,256,512,1024,2048. Each experiment/attempt is logged, with failed quality/timeout/OOM included. Choose the fastest validation **mean of >=3 complete runs** among methods passing the frozen gates, freeze code/source hashes, then evaluate holdout. Do not adapt after seeing holdout results.

Use CPU affinity [0,1] as provided; BLAS/OMP threads=2 for all workers. A reference not internally multithreaded remains available beside the two-thread native reference. No GPU, no simultaneous benchmark workers, no warmed-process headline, no OS cache clearing claim. Fresh interpreter startup, imports, checkpoint reading, IDX.gz decoding, normalization, predictions/voting and all output writing are charged using parent `perf_counter` from spawn to process exit. Split index construction/common pre-trained model construction are setup, not repeated inference. All systems receive the same raw image file and indices, write all labels and metadata. Every worker computes its own accuracy only **after** producing predictions, including on holdout after candidate freeze; that preprocessing/scoring/output cost is inside cold time. Candidate prediction functions never receive labels. The frozen evaluator independently recomputes pairwise quality after both output files exist. Its common comparison/read cost is measured and added equally to baseline/method primary endpoint times; raw cold times are also retained.

Final primary result: **one full cold speedup = sum(selected baseline times)/sum(frozen chosen method times)** on holdout, **5 paired repetitions**, balanced order, predetermined seed order. Mean, range, SD and descriptive 10,000 paired bootstrap 95% CI (seed=20261017) are reported. Repetitions measure execution variability on one fixed dataset, **not independent data-generalization evidence**. If quality gate fails, the speed is not called a lossless result. All other timings/ablations are labeled SECONDARY. If no method passes, honest primary result is no verified improvement, never select a lucky subset.

## Time / checkpoints / integrity

Start is `start_time.json`, first tool action after authorization; budget 5400 real seconds. Before every stage use the clock tool and append work_log. At elapsed 1800,3600,5100, record measured vs calculated vs presumed values, main risk and subjective verification probability in checkpoints.md. Automated monitor records actual observation time, no invented timestamps or exact-deadline assertions if late. No early final report; prepare report in advance and gate final sealing on **both wall and monotonic >=5400**. Use remaining time for real ablations/new runs, not sleep/busy-wait. Stop numerical work by deadline; disclose publication overhead honestly.

Protocol/evaluator/initial reference code hashes are sealed before first baseline prediction and before t=600. The evaluator is never modified after sealing; any evaluator bug is disclosed and invalidates the affected study rather than silently changing the pass rule. Reproduction can take longer than this research budget because shared model training is real and charged separately.
