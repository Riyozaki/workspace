# Agent 3D modeling benchmark

The benchmark compares the same prompt/reference/target profile across deterministic code modeling, external providers and future GPU backends.

## Scoring (0–5 each)

1. prompt/shape fidelity;
2. dimensions and proportion fidelity;
3. silhouette across required views;
4. topology quality;
5. PBR material/texture quality;
6. target budget and runtime performance;
7. editability/part naming;
8. interoperability and standards validation;
9. manufacturing fitness where applicable;
10. provenance, licensing and reproducibility.

A candidate cannot score above 2 overall if it fails format validation, has nonfinite geometry, hides missing geometry from the hero view, or violates an explicit dimensional requirement.

## Evidence bundle

Each run should retain outside Git:

- input prompt and references with licenses;
- dimensional brief and assumptions;
- backend/provider/model/version/seed;
- source and final hashes;
- GLB/STEP/STL outputs as applicable;
- structural/topology reports;
- front/right/back/perspective renders;
- contact sheet;
- blinded human ratings;
- runtime/cost.

The generated example in `examples/modeling/lounge-chair.json` is an engineering smoke test, not a substitute for a licensed external benchmark corpus.
