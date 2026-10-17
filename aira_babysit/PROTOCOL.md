# Autonomous worker v0.1 — honest boundaries

This release organizes a resumable LANGUAGE-data pipeline. It does NOT claim that
SmolLM2 GGUF is trainable by this worker or that an external teacher is connected.

- A run freezes its config, student GGUF SHA, task pools and generator/verifier
  source hashes before student attempts. Train/development/holdout template
  families are distinct. Full episodes stay together; no holdout export to training.
- The current local provider is verified_offline: integer arithmetic/grounded JSON
  plus topic-shift histories. It is an executable narrow teacher, NOT a frontier AI.
  external_required without a configured provider ends BLOCKED_TEACHER, not success.
- Budget is MAXIMUM cumulative active worker wall time, not a requirement to burn
  a whole hour. Paused/external waiting stops the process. Crash recovery may add
  a separately labeled conservative budget charge, never fabricate elapsed work.
- SQLite checkpoints, per-run leases plus a global worker file lock prevent duplicate
  runs. Committed task IDs are not regenerated on resume. Pause/stop checked during
  streaming. HTTP work is bounded; timed/native operations are cooperatively stopped.
- Serving is cooperatively yielded for0.2s after real examples; resource backoff/yield
  counts toward active WALL budget, not CPU-time or an acceleration claim.
- All student attempts, failures, corrected/replay examples and stage events retained.
  Only train failures/replay enter the training file. Development never supplies
  training examples; holdout is kept for a future final release, not queried each round.
- Current real default execution collects student replies, verifies offline teacher
  targets and creates a checksummed Kaggle bundle. Then it stops WAITING_TRAINING.
  training_executed=false, learning_cycle_complete=false. No synthetic training result.
- A training receipt is not proof of deployment quality. Returned artifacts require
  independent candidate evaluation, then explicit promotion; production model is never
  silently replaced. The Kaggle trainer is a separately marked integration target;
  no executed GPU-training claim without a real run.
- Secrets are not in specs/events/exported files. This chat is not a callable
  autonomous teacher API. Paid/remote teacher work requires explicit provider setup
  and a new approved budget. No arbitrary shell/model-generated code execution.
