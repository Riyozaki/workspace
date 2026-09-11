#!/usr/bin/env python3
"""Check preservation and exact packaging; not literary or medical certification."""
from pathlib import Path
from urllib.parse import unquote
import hashlib
import json
import re
import subprocess

P = Path(__file__).resolve().parents[1]
R = P.parents[1]
BASE = 'c342d3c235d9345e2d3abc1bc7950d5638b00dbe'
BRANCH = 'arena/01a08101-workspace'
REPORT = P / 'review/ch-16-v2-check.json'


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
prefix = (P / 'drafts').relative_to(R).as_posix() + '/'
for name in git('ls-tree', '-r', '--name-only', BASE, '--', prefix).decode().splitlines():
    f = R / name
    if f.name == 'README.md':
        continue
    assert f.read_bytes() == git('show', f'{BASE}:{name}'), name
    preserved[name] = sha(f.read_bytes())
assert len(preserved) == 20
active = [P / f'drafts/ch-{n:02}/ch-{n:02}-v{3 if 8 <= n <= 10 else 2}.md' for n in range(1, 17)]
for f in active:
    assert not re.search('костяш', f.read_text(), re.I), f
old = (P / 'book/03-manuscript/arc-01/ch-01.md').read_bytes().splitlines(keepends=True)[:111]
new = active[0].read_bytes().splitlines(keepends=True)[:111]
assert old == new
assert (P / 'drafts/arc-02/arc-02-v3.md').read_text() == '\n\n'.join(f.read_text().rstrip() for f in active[5:10]) + '\n'

chapter = active[-1]
source = P / 'book/03-manuscript/arc-03/ch-16.md'
text = chapter.read_text()
assert text.startswith('# Глава 16\n\n') and text.endswith('\n')
assert '\ufffd' not in text and '\x00' not in text
assert not re.search(r'(?m)[ \t]+$', text)
for line in text.splitlines():
    assert line.count('*') % 2 == 0, line
for stale in ('Сухой Брод', 'Тобер', 'Союз Свободных Дверей'):
    assert stale not in text, stale

pairs = json.loads((P / 'review/ch-16-before-after.json').read_text())
assert len(pairs) == 2
rendered = (P / 'review/ch-16-before-after.md').read_text()
verified = []
for pair in pairs:
    assert pair['before_path'] == 'book/03-manuscript/arc-03/ch-16.md'
    assert pair['after_path'] == 'drafts/ch-16/ch-16-v2.md'
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
        if target:
            resolved = (f.parent / target).resolve()
            assert resolved.exists() or resolved == REPORT, (f, link)
            links += 1

refinements = json.loads((P / 'review/ch-16-v2-refinements.json').read_text())
assert len(refinements) == 66
reconstructed = text
for edit in reversed(refinements):
    assert reconstructed.count(edit['after']) == 1, edit['reason']
    reconstructed = reconstructed.replace(edit['after'], edit['before'], 1)
initial_hash = sha(reconstructed.encode())
assert len(reconstructed) == 40712 and len(reconstructed.split()) == 6549
cache = R / '.cache/ch16/initial.md'
if cache.exists():
    assert initial_hash == sha(cache.read_bytes())
assert (len(text), len(text.split()), len(text.splitlines())) == (41005, 6591, 1017)

report = dict(
    scope='Technical preservation and exact packaging only; not literary or medical certification.',
    branch=BRANCH,
    preservation_baseline_commit=BASE,
    comparison_baseline='Selected September chapter 16; no previously delivered new chapter 16 existed.',
    imported_files_checked=397,
    changed_or_missing_imported_files=[],
    previously_tracked_drafts_unchanged=preserved,
    author_wording_corrections_already_in_preservation_baseline=True,
    unwanted_word_absent_in_all_16_current_chapters=True,
    protected_ch01_opening_lines_1_111_byte_identical=True,
    arc02_v3_chapter_bodies_exact=True,
    source_ch16=stats(source),
    new_ch16=stats(chapter),
    comparisons=verified,
    local_markdown_links_checked=links,
    formatting_checks_passed=True,
    contextual_refinement_operations=66,
    initial_draft_reconstructed_sha256=initial_hash,
    refinement_sequence_reverse_replayed=True,
    reading_boundary='Selected source 11–17 previously read in stages; source 16 freshly reread fully. New 16 read fully twice (initial and after 51 operations); final 15 edits read in local context. Source 17 first 155 lines freshly read; not a full fresh reread. Current 12 permission/Mabrik/weapon passages checked locally. Earlier author PDF 17 not examined; must be read separately before new 17. New 17 not yet written.',
)
REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(f'PASS: 397 imports, {len(preserved)} prior prose/collection files unchanged, protected opening, exact arc02 v3, 2 exact comparisons, {links} local links, 66 reversibly logged refinements, formatting, unwanted-word check on 16 active chapters.')
