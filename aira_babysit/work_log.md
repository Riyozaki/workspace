# Autonomous Babysit orchestration work log

User requests a process that can be left running under an hour-scale budget and
later encompass learning on Kaggle. No hour-long real training was authorized or
claimed here. Existing serving prototype v0.2 and all historical research stay
unchanged. Default worker must stop honestly when training/teacher is unavailable.

Scope fixed in PROTOCOL.md before the first worker/integration smoke:
real current LM replies, verified synthetic training targets, durable jobs,
pause/stop/resume, artifact handoff, GPU-trainer contract and explicit limits.
No router training is substituted for language-model SFT.

## Executed evidence

- Initial real CLI data-phase6 examples completed, not training; original log retained under artifacts.
- Final frozen-source browser run `f270246ca9e74222`:12 real student calls committed uniquely, pause after1, resume, active wall 15.143745s, WAITING_TRAINING.
- Student synthetic TRAIN passes0/12; verified teacher targets12/12. This is not a claim of language improvement.
- Instrumented real HTTP pause-before-commit/resume also passed; no mocked native inference.
- Combined88 Python tests,10 transport tests and embedded/mobile dashboard checks executed.
- Packaged no-Torch bundle preflight executed. Actual GPU SFT, strong-teacher API, checkpoint return, independent candidate evaluation and multi-round promotion remain unexecuted/unimplemented gates.
- Old application/research137 sealed files verified byte-identical before new publication metadata.
