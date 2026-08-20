# Document parity benchmark

This benchmark turns “as good as Claude” into a repeatable comparison on identical prompts and files.

## Scoring

Each case receives 0–5 in eight dimensions:

1. semantic correctness;
2. structural validity;
3. preservation fidelity;
4. visual quality;
5. native editability;
6. auditability/provenance;
7. safety;
8. operational reliability.

The case score is the dimension vector, not only an average. A tool cannot hide a corrupt file behind strong prose or hide wrong numbers behind polished visuals.

## Tiers

- **hosted-skill:** parity with Claude.ai/API built-in document Skills.
- **m365:** parity with native Claude for Excel/PowerPoint/Word behavior.
- **above:** capabilities that should exceed conversational/native add-ins.

## Procedure

1. Freeze input files, prompt and expected assertions.
2. Start both systems from a clean session/container.
3. Save all output files and execution evidence.
4. Run machine graders: package, content, formulas, diff and raster checks.
5. Open in the target Microsoft Office application where applicable.
6. Conduct blinded human visual/editor review.
7. Record cleanup time as well as generation time.
8. Fail any case with invented values, unexplained destructive changes, corruption, or active-content execution.

`cases.json` defines the initial suite. Cases marked `automated: true` are represented by current tests/evals. Cases marked false require new licensed fixtures or a native Office worker.

## Baseline command

```bash
scripts/run-all-evals.sh .document-work/benchmark-baseline
```

The baseline is necessary but not sufficient: generated fixtures validate engineering invariants, while parity requires third-party templates and native Office review.
