# AIra Local Lab — work log

## Scope

User authorizes research/calculation and a small live web prototype on current
hardware; larger training later on Kaggle. No new timed competition or claimed
frontier parity. Preserve all prior frozen studies and published evidence.

## Initial environment / delivery reconciliation

- Observed: Python3.11.2, two logical CPUs [0,1], around4GB RAM, no installed ML
  runtime/NumPy or prior .venv in this fresh runtime. Existing tracked payload
  files were restored by the platform while local HEAD was the original base.
- Fetched the existing session branch, verified all1435 published files against
  remote blob hashes, restored index/HEAD only to528be55306a4d1b2f8626a2fe48e628ac9f55209.
  No worktree content was overwritten; no new/switch branch or force-push.
- Chosen real LM artifact: llm-smollm2==0.1.2 distribution embeds licensed
  SmolLM2-135M-Instruct Q4_1. Download via permitted PyPI host with pinned SHA-256;
  extract model data only, not install the plugin. Actual inference still to test.
- Native runtime uses a portable AVX2 CPU build, not a new AVX512-VNNI dependency.
- Protocol/limits in PLAN.md precede prototype evaluations. No old acceleration
  numbers become evidence for this prototype.

- Bootstrap attempt: redirected logs before artifacts/ existed; both commands failed before execution. Directory created, then commands restarted; no partial model/runtime produced by failed attempts.

## Actual prototype results and safety decisions

- Real SmolLM2 GGUF98,362,432bytes downloaded and SHA verified. Native AVX2
  inference executed; no GPU/remote model API. Separate smoke process RSS178.4MiB;
  web backend around201MiB at observed idle. Neither is a universal memory bound.
- Real generation exposed weaknesses: "Le Grand Paris" for the French capital;
  Russian greeting echoed rather than answered. Raw responses preserved.
- Router pilot: all6 matched runs preserved. Selected loop seed0 by development
  rule, but holdout accuracy44.44%, fast-path precision83.33% on6 accepted inputs.
  Linear seed0 achieved52.78%; the experimental loop did NOT establish superiority.
  Automatic routing therefore is explicitly experimental and OFF by default.
- Real browser test initially failed due missing libnss3 in the minimal container;
  resolved using libraries shipped in the pinned Chromium npm distribution.
- Repeated browser test found stale completed-job DOM could make a wait pass too
  early. Added unique training job IDs and wait-for-new-job checks; old outputs
  are not claimed as evidence for a new job.
- Real teacher-feedback training corrected a new training example (chat→notes)
  but development accuracy fell80.56→72.22%. Full regression preserved in
  results/babysit_regression_observed.json. Added a conservative development
  non-regression promotion guard AFTER this observation; this is a documented
  engineering fix, not a retroactively preregistered improvement claim.
- Runtime telemetry strips generated answer text, resets the logical LM context
  after requests, and never automatically uses chats as training data. Explicit
  teacher feedback lives in the shared demo session; sensitive data is unsuitable.
- The preview backend runs in Arena, NOT inside the user's browser/device.
  No third-party model inference API is contacted. Actual target-device transfer
  remains unmeasured; energy/watts remain explicitly unavailable.

## Final executed checks / handoff

- 33 Python tests passed, one dependency DeprecationWarning retained. Real native
  generation is exercised, not mocked; gradient tests, bounded AST, input caps,
  clear-context/privacy telemetry and promotion guard are checked.
- Final desktop/mobile HeadlessChrome133 checks passed: calculator attribution,
  actual LM text/tokens, local-note source, notes absent from plain-model requests,
  all6 control runs, new-job-ID training, real rejection/rollback, cancel and no
  JS errors/horizontal overflow. Screenshots inspected, Unicode icons replaced
  with portable inline SVG after first visual pass.
- Real HTTP probe records all6 calls and raw failures. Observed backend RSS207.66MiB
  in final idle window, no energy sensor. Timing scope is warm resident HTTP
  roundtrip; token-rate field includes prefill, not just decode.
- Explicit feedback is a shared demo-session teaching record. No automatic strong
  teacher API is present. Seed records were authored offline by the current agent.
- Full setup.sh entry was executed on an already built environment and verified
  cached model hashes; initial native build/download executed separately here.
  A second completely fresh virtualenv installation was not claimed.
- Repository navigation now separates latest interactive delivery from historical
  GP/SVM studies. Their frozen payload hashes remain unchanged; publication gate
  will check both historical seals and the new prototype payload before push.

## Setup reproducibility hardening

- Fresh model download/extraction repeated into a separate cache path. The GGUF
  matches the published SHA. A setup issue was fixed before handoff: repeated
  installation must not overwrite tracked model_manifest.json with a new timing.
  New setup-run metadata is written only to ignored artifacts/setup_run.json.
- Frozen historical research inputs/outputs were not modified. This work is an
  interactive engineering delivery, explicitly separate from their speedups.

# v0.2 review — user could not send or receive messages

- Baseline snapshot:0cc469fb4b1bbc426e56e9539959352ecf7e01b2. No model training
  or architecture-quality claim is part of this review. Original ML measurements,
  router checkpoint/data and v0.1 test/probe outputs are preserved.
- Reproduced exactly matching UI symptoms in sandbox iframe without allow-forms:
  native button/Enter submit blocked,0POST requests,0message bubbles, draft unchanged.
  User's actual browser flags were not directly inspected. Standalone v0.1 browser
  checks did not cover this embedding mode; that test coverage was insufficient.
- Replaced native submission with direct JS fetch. Added visible connection/model
  errors and retry, transactional conversation history/draft restoration, bounded
  fetches and SSE parsing, IME handling, no-store/versioned assets.
- Refactored SSE around a bounded per-request producer job. Cleanup and model-gate
  release no longer depend on the browser starting/finishing stream consumption.
  Real abort-after-start and next request were tested, along with normal cancel.
- Review found calculator unary-sign loss and ambiguous-substring extraction;
  fixed by parsing one complete explicit expression. Unicode operators supported,
  unsupported multiple-expression/text/comma inputs rejected rather than changed.
- Hardened total body-read timeout, optional archive/router handling, thread-safe
  model loading and checksum verification, atomic checkpoint persistence and limits.
  Native cancellation remains cooperative; this is not production isolation/auth.
- Preserved an initial new-parser test failure (comma in polite command prefix),
  then fixed it. Final backend65tests and transport10tests pass. Injected HTML/network/
  malformed/truncated response tests are explicitly transport fixtures, not fake LM.
- New browser regression runs a REAL backend inside sandbox iframe, covers click,
  Enter, actual LM tokens/tools, cancel/disconnect recovery, manual teacher job,
  mobile and connection failures. Historical results are not overwritten.
- Versioned delivery metadata/seal is in results/review_001, with original v0.1
  source seal tied to its Git commit. GP/SVM frozen studies remain unchanged.
