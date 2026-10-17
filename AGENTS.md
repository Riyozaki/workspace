# Repository delivery instructions

## Publishing requested repository changes

The user requires completed repository changes to be delivered to the working
branch, not left only in the sandbox. Unless the user explicitly requests local
work only or forbids commit/push:

1. Work only on the branch fixed by the active Arena session/developer instructions.
   Never create/switch/push another branch and never force-push.
2. Keep the root README and publication.json pointing to the actual latest study.
   Label older experiments as historical; do not merge their performance claims.
3. Preserve frozen protocols, evaluators, numerical sources, raw measurements,
   failed attempts and published study seals. If navigation replaces a historically
   sealed document, archive its original bytes and explicitly record the path
   mapping without changing historical expected hashes.
4. Include all non-ignored code, tests, reports, CSV, raw JSON and verification logs.
   Respect .gitignore: virtual environments, caches, downloaded corpora, generated
   model checkpoints and temporary builds remain outside Git and reproducible.
5. Run `bash scripts/publish.sh "<descriptive commit message>"` (or equivalent
   explicit checks/add/commit/push steps). The script defaults to this session's
   branch; a different active session must pass its developer-prescribed branch
   via ARENA_WORK_BRANCH, never invent a branch.
6. Delivery is complete only after push succeeds, remote branch SHA equals local
   HEAD, and `git status --short` is empty. Do not claim "published/pushed" based
   only on local file writes or a local commit.
7. Give the user direct links to the committed latest report and the commit SHA.
   If push/authentication fails, report the failure clearly; ask for GitHub
   reconnection in Arena where appropriate, never for passwords/tokens.

Discussion/review-only requests with no file changes do not require a new commit.
These instructions do not authorize altering measurements or strengthening
scientific claims merely to make publication checks pass.
