# Mathematics, cost model and scope

Numerical theory here is **РАССЧИТАНО**, never a hardware-counter measurement. Actual timings/quality belong to results files. There is no structural/separable-kernel assumption: support vectors are arbitrary 784-dimensional clothing images.

## Same trained multiclass SVM

For support vector s_j and input x, `K(x,s_j)=exp(-gamma ||x-s_j||²)`.
For classes a<b the public libsvm model computes

`f_ab(x) = sum_{j in SV_a} dual[b-1,j] K(x,s_j) + sum_{j in SV_b} dual[a,j] K(x,s_j) + intercept[pair(a,b)]`.

If f_ab>0 vote for a, otherwise b. Return the earliest class with maximal votes. All 45 pairs, all support vectors, the same C/gamma/coefficients and the same tie rule are retained. No retraining, pruning, distillation or cached predictions is used. Public binary sklearn coefficient sign is handled separately in unit tests; the task itself has 10 classes.

Batching uses `||x-s||²=||x||²+||s||²−2 x·s` and a Q-by-S kernel matrix in blocks. A sparse logical coefficient matrix has S*(C−1) nonzeros; using dense S-by-45 BLAS costs extra arithmetic but eliminates scalar reductions. This is established linear algebra, not a new SVM.

## Exact integer pixel distances

Training preprocessing was `float64(pixel)/255`. All original support pixels are reconstructed and checked with **exact float64 equality** before compact export. For original uint8 a,b:

`||a/255−b/255||² = (sum a_i² + sum b_i² − 2 sum a_i b_i)/65025` over real arithmetic.

All integer dot products/norms are exact. With D=784, `D*255²=50,979,600 < 2³¹`; even intermediate `2*dot` is below 2³¹. This is **not lossy int8 quantization of the pixels**. In the selected serving system, scaling and vector exp are **float32**, followed by **float64 FMA decision accumulation**. Thus the complete numerical method is mixed precision, not an exact IEEE-equivalent classifier. A separate float64-exp path remains for numerical tests. Accuracy/agreement of the actual mixed-precision serving path are empirically checked by the frozen evaluator.

AVX512-VNNI computes unsigned a times signed (b−128). Correct with `128*sum(a)`. Pack 16 support vectors per lane group, four coordinates per 32-bit accumulator. A microtile reuses each 64-byte packed SV load across multiple queries. Masked stores handle the final SV tail; query tails are computed safely and only valid rows are written. Unit tests include all-255 overflow bounds, non-multiple-of-16 support counts and non-multiple-of-tile query counts, compared against independent int64 NumPy multiplication.

## Arithmetic / memory

Observed shared model S=18,802; Q=5,000, D=784, C=10 are fixed task sizes. **РАССЧИТАНО**:

- Dot-product leading arithmetic: `2QSD = 147,407,680,000` real-operation equivalents. Integer operations are not FLOPs and are never relabeled measured GFLOP/s.
- Initial dense coefficient GEMM: `2QS*45 = 8,460,900,000` leading FLOPs. The selected native path uses the nine logical coefficients per SV, padded to 16 SIMD lanes: about `2QS*16 = 3,008,320,000` leading double-operation slots. The mathematical sparse minimum is `2QS*9 = 1,692,180,000`. Extra SIMD lanes trade arithmetic for throughput; no full kernel float64 cast remains in the selected path.
- Kernel entries / exp calls: `QS=94,010,000`.
- Full float64 kernel array: **752,080,000 bytes**; full float32: **376,040,000 bytes**. Blocking reduces this to O(BS), not O(QS). The initial non-fused compact prototype used `4BS + 8BS` temporary bytes. The **selected fused path** writes only the `4BS` float32 kernel block, then directly reduces it in float64 without an integer-dot matrix or float64 kernel cast; score output is `8B*45` bytes plus tiny native accumulator/metadata workspace.
- Original double SV values: `8SD=117,926,144 bytes`; original uint8 values: `SD=14,740,768 bytes` before tail padding. The selected compact artifact additionally contains **16 padded float64 coefficient slots per SV** (nine logical coefficients), intercept/classes/gamma, class/pair indices and int32 norms. Actual file size/RSS are measured separately, not confused with this ideal payload.

## Amdahl and roofline

For fraction f of the **whole cold endpoint** accelerated by s, `S_total=1/((1−f)+f/s)`. Even an infinite dot-product speedup cannot bypass imports, checkpoint load, IDX decompression, normalization, exp, voting and output. No ratio of dot-product FLOPs is called full-system speedup.

Original per-query SV rereads are potentially O(QSD) bytes; GEMM/packed microtiles reuse weights. Conditional bandwidth estimates require actual cache/memory behavior and are **ПРЕДПОЛОЖЕНО** unless separately calibrated. Strong ONNX runtime is not presumed naive: its actual code and measured full requests are inspected, and the fastest eligible ready reference is the baseline.

## One-time preparation and amortization

The primary task is **inference of a pre-trained model**, not training+inference. Shared SVC training, native/ONNX export, compact packing and native-library compilation are recorded explicitly. For one-time additional preparation P and R inference requests, method total is `P+R*T_method` and relative serving gain is `R*T_baseline/(P+R*T_method)`; break-even R is `P/(T_baseline−T_method)` when baseline is slower. P/R cannot be silently dropped from a claim about first-ever deployment.

Any table formed by adding separately measured training/serialization/request stages is labeled **РАССЧИТАНО**, not a measured complete training+inference run. Download/installation/build scope and pre-existing artifact cache must be stated. Model-format packing is a legal model representation transform, not a prediction cache.

## Quality/statistical scope

Accuracy non-inferiority is baseline−0.001 absolute, plus prediction agreement >=0.999. No score/probability/calibration guarantee is claimed. Float32 candidate is approximate arithmetic; compact uint8 integer distance is exact before float64 exp/decisions. Test label agreement is not a substitute for accuracy: both frozen gates must pass.

Five paired timing repetitions describe VM execution variation on one fixed holdout. A paired bootstrap CI does not quantify dataset shift, new model randomness or unseen domains. A locally sequestered public split is not independent organizer verification; real external verification remains unperformed.
