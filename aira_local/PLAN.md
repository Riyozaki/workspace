# AIra Local Lab — scope fixed before prototype tests

This is a new practical prototype, NOT another claim of 50x speedup and NOT a new
frontier-quality language model. No 90-minute research window was requested.

## What will actually run

1. A real pretrained SmolLM2-135M-Instruct Q4_1 on CPU, one inference thread,
   fixed bounded context/output, local-only runtime, visible failure/quality limits.
   It is the pretrained control, not our architecture or our training result.
2. A genuinely trainable tiny intent router (linear control + shared-weight
   iterative MLP experimental variant), trained here on authored RU/EN examples.
   It only chooses among calculator, local-note retrieval, and language model.
   It is NOT a language model and cannot establish large-LM capability scaling.
3. AI Babysit pilot: inspect student mistakes, human-readable teacher corrections,
   verified synthetic seed examples, train/router feedback and JSONL export.
   No claim that the quantized language model has been fine-tuned here.

## Frozen pilot evaluation rules

Router train/development/holdout separated by prompt family, with literal
hand-authored holdout phrasings excluded from training and calibration. Seeds
0,1,2. Compare linear vs iterative model with fixed optimizer-step budget.
Choose deployment model/abstention threshold using development only. Holdout
is not fed back into training. Report coverage, routed precision, accuracy,
macro-F1, parameter count and observed request time. Failure to improve over
linear is a valid negative result, not a reason to hide the control.

Language-model smoke/evaluation is a small explicit engineering check, not a
frontier benchmark: basic factual/format prompts, arithmetic checked by a tool,
separate RU/EN failures, bounded token generation. Never hardcode LM answers.

## System constraints and safety

Two logical CPU threads, around 4GB RAM, no GPU in the observed environment.
One active generation; one native inference thread; bounded context and output;
working cancel; no arbitrary shell/file/network tools. Calculator uses a bounded
AST interpreter, never eval(). Notes are explicit request data, not filesystem
access. User chats are not silently added to training data.

Telemetry must distinguish sampled process RSS/CPU, actual generated-token count,
server request latency and first-content latency. No joules/watts without a real
energy sensor. Download/build cost is setup, not per-token inference; disclose it.

## Deliverable

A working live web preview; reproducible setup/start/test commands; authentic
model/data provenance; tests and real measured outputs; a clear boundary between
pretrained LM, trained router and deterministic tools. Numerical claims from old
GP/SVM studies are not reused. Finish by commit/push/remote-SHA verification on
the existing Arena branch; update repository navigation without altering old seals.
