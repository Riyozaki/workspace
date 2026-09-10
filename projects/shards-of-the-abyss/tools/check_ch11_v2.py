#!/usr/bin/env python3
"""Integrity and packaging checks only; does not edit or assess literary prose."""
from pathlib import Path
from urllib.parse import unquote
import hashlib
import json
import re
import subprocess

P = Path(__file__).resolve().parents[1]
R = P.parents[1]
BASE = 'bad1986a3616d2c86b39d89e448868b785690923'
BRANCH = 'arena/01a08101-workspace'
REPORT = P / 'review/ch-11-v2-check.json'

def git(*args):
    return subprocess.check_output(['git', *args], cwd=R)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def stats(path):
    data = path.read_bytes()
    text = data.decode('utf-8')
    return dict(sha256=sha(data), characters=len(text), whitespace_words=len(text.split()), lines=len(text.splitlines()))

assert git('branch', '--show-current').decode().strip() == BRANCH
manifest = json.loads((P / 'IMPORT.json').read_text())
assert len(manifest['files']) == 397
for item in manifest['files']:
    assert sha((P / 'book' / item['path']).read_bytes()) == item['sha256'], item['path']

preserved = {}
prefix = str((P / 'drafts').relative_to(R)) + '/'
for name in git('ls-tree', '-r', '--name-only', BASE, '--', prefix).decode().splitlines():
    f = R / name
    if f.name == 'README.md':  # Navigation is intentionally updated for the new chapter.
        continue
    assert f.read_bytes() == git('show', f'{BASE}:{name}'), name
    preserved[name] = sha(f.read_bytes())
assert len(preserved) >= 10
old = (P / 'book/03-manuscript/arc-01/ch-01.md').read_bytes().splitlines(keepends=True)[:111]
new = (P / 'drafts/ch-01/ch-01-v2.md').read_bytes().splitlines(keepends=True)[:111]
assert old == new
chapters = [P / f'drafts/ch-{n:02}/ch-{n:02}-v{2 if n < 8 else 3}.md' for n in range(6, 11)]
assert (P / 'drafts/arc-02/arc-02-v3.md').read_text() == '\n\n'.join(f.read_text().rstrip() for f in chapters) + '\n'

chapter = P / 'drafts/ch-11/ch-11-v2.md'
source = P / 'book/03-manuscript/arc-03/ch-11.md'
text = chapter.read_text()
assert text.startswith('# Глава 11\n\n') and text.endswith('\n')
assert '\ufffd' not in text and '\x00' not in text
assert not re.search(r'(?m)[ \t]+$', text)
for line in text.splitlines():
    assert line.count('*') % 2 == 0, line
for stale in ('Сухой Брод', 'Тобер', 'Союз Свободных Дверей'):
    assert stale not in text, stale

pairs = json.loads((P / 'review/ch-11-before-after.json').read_text())
assert len(pairs) == 2
rendered = (P / 'review/ch-11-before-after.md').read_text()
verified = []
for pair in pairs:
    assert pair['before_path'] == 'book/03-manuscript/arc-03/ch-11.md'
    assert pair['after_path'] == 'drafts/ch-11/ch-11-v2.md'
    result = {'title': pair['title']}
    for side in ('before', 'after'):
        body = (P / pair[side + '_path']).read_text()
        quote = pair[side]
        assert body.count(quote) == 1, (pair['title'], side)
        assert rendered.count(quote) == 1, (pair['title'], side, 'markdown copy')
        start = body[:body.index(quote)].count('\n') + 1
        result[side] = dict(path=pair[side + '_path'], exact_contiguous=True,
                            lines=[start, start + quote.count('\n')], sha256=sha(quote.encode()))
    verified.append(result)

files = [R / x for x in ('README.md', 'NOW.md', 'AGENTS.md', 'ABOUT.md')]
files += [f for f in P.rglob('*.md') if 'book' not in f.relative_to(P).parts]
links = 0
for f in files:
    for link in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)', f.read_text()):
        if re.match(r'\w+://|mailto:|#', link):
            continue
        target = unquote(link.split('#')[0])
        if not target:
            continue
        resolved = (f.parent / target).resolve()
        assert resolved.exists() or resolved == REPORT, (f, link)
        links += 1

refinements = json.loads((P / 'review/ch-11-v2-refinements.json').read_text())
assert len(refinements) == 55
report = dict(
    scope='Technical integrity and exact packaging, not a literary or medical certificate.',
    branch=BRANCH,
    preservation_baseline_commit=BASE,
    comparison_baseline='September source chapter 11; no previously delivered new chapter 11 existed.',
    imported_files_checked=397,
    changed_or_missing_imported_files=[],
    previously_tracked_drafts_unchanged=preserved,
    protected_ch01_opening_lines_1_111_byte_identical=True,
    arc02_v3_chapter_bodies_exact=True,
    source_ch11=stats(source),
    new_ch11=stats(chapter),
    comparisons=verified,
    local_markdown_links_checked=links,
    formatting_checks_passed=True,
    contextual_refinement_operations=55,
    reading_boundary='All selected source 11–17 read in multiple stages; source 11 reread. New 11 read fully twice; final 17 edits read in local context. Earlier PDF 17 not read. No new 12–17 prose.',
)
REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(f'PASS: 397 imports, {len(preserved)} prior draft files unchanged, protected opening, exact arc02 v3, 2 exact pairs, {links} local links, new chapter formatting.')
