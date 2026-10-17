#!/usr/bin/env bash
# Deliver all non-ignored repository changes and verify the actual remote tip.
set -euo pipefail
cd "$(dirname "$0")/.."
expected_branch="${ARENA_WORK_BRANCH:-arena/01a0f7e1-workspace}"
branch="$(git branch --show-current)"
if [[ "$branch" != "$expected_branch" ]]; then
  printf 'Refusing publication: current branch %s, required session branch %s\n' "$branch" "$expected_branch" >&2
  exit 1
fi
message="${1:-Publish verified research updates}"
git add --all
python3 scripts/verify_publication.py --require-tracked
# Keep upstream source snapshots and raw failure logs byte-for-byte. Their
# integrity is checked above; do not "fix" historical evidence for style lint.
git -c core.whitespace=cr-at-eol diff --cached --check -- . \
  ':(exclude)competition50x/references/**' \
  ':(exclude)competition50x/results/**' \
  ':(exclude)aira_local/results/**' \
  ':(exclude)competition50x/versions/**' \
  ':(exclude)research/archive/**'
if ! git diff --cached --quiet; then
  git commit --quiet -m "$message"
fi
git push origin "$branch"
local_sha="$(git rev-parse HEAD)"
remote_line="$(git ls-remote --heads origin "refs/heads/$branch")"
remote_sha="${remote_line%%[[:space:]]*}"
if [[ "$local_sha" != "$remote_sha" ]]; then
  printf 'Remote verification failed: local=%s remote=%s\n' "$local_sha" "$remote_sha" >&2
  exit 1
fi
remaining="$(git status --porcelain)"
if [[ -n "$remaining" ]]; then
  printf 'Changes remain after publication:\n%s\n' "$remaining" >&2
  exit 1
fi
printf '\nPublished and verified: %s\nCommit: %s\nWorking tree: clean\n' "$branch" "$local_sha"
