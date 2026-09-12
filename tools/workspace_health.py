#!/usr/bin/env python3
"""Read-only, bounded workspace audit. No repair, fetch, staging or background work.

  python tools/workspace_health.py
  python tools/workspace_health.py --remote --require-clean
  python tools/workspace_health.py --base COMMIT --verify-base --allow-changed NOW.md
  python tools/workspace_health.py --json > .cache/health.json

--verify-base compares all baseline file contents, including ignored/tracked sources;
--allow-changed only permits edits, never missing baseline files. Extra files are
reported, not rejected. Git diff attributes do not bypass the content verification.
All subprocesses have a timeout. Network access occurs only with --remote.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
BRANCH = 'arena/01a08101-workspace'
SESSION_BASE = '53a742e17d8f10845b37f938253529c8382d6d48'
STARTUP = ['AGENTS.md', 'NOW.md', 'README.md',
           'projects/shards-of-the-abyss/README.md',
           'projects/shards-of-the-abyss/drafts/README.md']


def git(*args):
    try:
        p = subprocess.run(['git', '--no-optional-locks', *args], cwd=ROOT, capture_output=True, timeout=25)
    except subprocess.TimeoutExpired as e:
        raise RuntimeError('Git command timed out; no repair attempted') from e
    if p.returncode:
        # Do not echo stderr: authenticated remote URLs can contain credentials.
        raise RuntimeError(f'Git {args[0]} failed (exit {p.returncode}); no repair attempted')
    return p.stdout


def blob_id(data, algorithm):
    return hashlib.new(algorithm, b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def entries(tree):
    for row in tree.rstrip(b'\0').split(b'\0'):
        if not row:
            continue
        metadata, name = row.split(b'\t', 1)
        mode, kind, oid = metadata.decode('ascii').split()
        yield mode, kind, oid, os.fsdecode(name)


def compare_base(base, allowed):
    algorithm = git('rev-parse', '--show-object-format').decode().strip()
    same, changed, missing, unsupported = 0, [], [], []
    total = 0
    for mode, kind, oid, name in entries(git('ls-tree', '-rz', base)):
        total += 1
        p = ROOT / name
        if kind != 'blob':
            unsupported.append(name)
            continue
        if not p.exists() and not p.is_symlink():
            missing.append(name)
            continue
        if (mode == '120000') != p.is_symlink():
            changed.append(name)
            continue
        data = os.fsencode(os.readlink(p)) if p.is_symlink() else p.read_bytes()
        if blob_id(data, algorithm) == oid:
            same += 1
        else:
            changed.append(name)
    unexpected = sorted(set(changed) - set(allowed))
    return {'total': total, 'unchanged': same, 'changed': changed,
            'missing': missing, 'unsupported': unsupported,
            'unexpected_changed': unexpected,
            'passed': not (missing or unsupported or unexpected)}


def measured(*args):
    runs = []
    result = b''
    for _ in range(3):
        t = time.monotonic()
        result = git(*args)
        runs.append(round(time.monotonic() - t, 6))
    return result, {'seconds_median': statistics.median(runs), 'bytes': len(result)}


def audit(args):
    branch = git('branch', '--show-current').decode().strip()
    head = git('rev-parse', 'HEAD').decode().strip()
    base = git('rev-parse', '--verify', args.base + '^{commit}').decode().strip()
    problems = []
    if branch != BRANCH:
        problems.append('Unexpected branch; do not stage or repair automatically')
    status, status_timing = measured('status', '--porcelain=v1', '-z', '--untracked-files=all')
    if args.require_clean and status:
        problems.append('Working tree is not clean')
    paths = [os.fsdecode(p) for p in git('ls-files', '-z').rstrip(b'\0').split(b'\0') if p]
    sizes = []
    groups = Counter()
    for name in paths:
        p = ROOT / name
        if p.is_file() and not p.is_symlink():
            n = p.stat().st_size
            sizes.append((n, name))
            group = '/'.join(Path(name).parts[:3])
            groups[group if name.startswith('projects/') else 'root/tools/docs'] += n
    # Small name/status output only, never emit a cumulative patch.
    diff_output, diff_timing = measured('diff', '--no-ext-diff', '--numstat', base, 'HEAD')
    numstat = diff_output.splitlines()
    text_rows = [r for r in numstat if not r.startswith(b'-\t-\t')]
    if text_rows:
        problems.append('Textual diff rows detected; check global -diff')
    attrs = git('check-attr', 'diff', '--', '__future_file__.md').decode().strip()
    if not attrs.endswith('diff: unset'):
        problems.append('Global diff suppression is not effective for a future file')
    disk = shutil.disk_usage(ROOT)
    startup = {p: (ROOT / p).stat().st_size for p in STARTUP if (ROOT / p).is_file()}
    result = {
        'captured_at_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'Sandbox/Git snapshot, not browser timings, UI health or literary QA',
        'branch': branch, 'head': head, 'base': base, 'clean': not bool(status),
        'tracked_files': len(paths), 'tracked_bytes': sum(n for n, _ in sizes),
        'groups_bytes': dict(groups),
        'largest_files': [{'bytes': n, 'path': p} for n, p in sorted(sizes, reverse=True)[:8]],
        'startup_bytes': startup, 'startup_total_bytes': sum(startup.values()),
        'disk_available_bytes': disk.free, 'status': status_timing,
        'numstat': {**diff_timing, 'changed_paths': len(numstat), 'text_rows': len(text_rows)},
        'git_objects': git('count-objects', '-v').decode().strip(),
    }
    if args.verify_base:
        result['preservation'] = compare_base(base, args.allow_changed)
        if not result['preservation']['passed']:
            problems.append('Baseline preservation check failed; inspect report before writing')
    if args.remote:
        t = time.monotonic()
        refs = git('ls-remote', '--heads', 'origin', 'refs/heads/' + BRANCH).splitlines()
        remote = refs[0].split()[0].decode() if len(refs) == 1 else None
        result['remote'] = {'head': remote, 'matches_head': remote == head,
                            'seconds': round(time.monotonic() - t, 6)}
        if remote != head:
            problems.append('Remote/HEAD mismatch; no automatic repair')
    result['problems'] = problems
    result['passed'] = not problems
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--base', default=SESSION_BASE)
    p.add_argument('--verify-base', action='store_true')
    p.add_argument('--allow-changed', action='append', default=[])
    p.add_argument('--remote', action='store_true')
    p.add_argument('--require-clean', action='store_true')
    p.add_argument('--json', action='store_true')
    args = p.parse_args(argv)
    try:
        r = audit(args)
    except (RuntimeError, OSError, ValueError) as e:
        print(f'Audit incomplete: {e}', file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(f"{'PASS' if r['passed'] else 'CHECK'} | {r['branch']} | {r['head'][:12]} | clean={r['clean']}")
        print(f"Files: {r['tracked_files']}; tracked size: {r['tracked_bytes']/1048576:.2f} MiB; free disk: {r['disk_available_bytes']/1073741824:.2f} GiB")
        print(f"Status median: {r['status']['seconds_median']:.4f}s; numstat median: {r['numstat']['seconds_median']:.4f}s; textual rows: {r['numstat']['text_rows']}")
        print(f"Entry documents: {r['startup_total_bytes']} bytes; no cumulative patch printed")
        if 'preservation' in r:
            v = r['preservation']
            print(f"Baseline: {v['unchanged']}/{v['total']} byte-identical; {len(v['changed'])} edited; {len(v['missing'])} missing; allowed-check={v['passed']}")
        if 'remote' in r:
            print(f"Remote=HEAD: {r['remote']['matches_head']} ({r['remote']['seconds']:.3f}s)")
        for problem in r['problems']:
            print('! ' + problem)
        print('This is not a measurement of the Arena page or browser.')
    return 0 if r['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
