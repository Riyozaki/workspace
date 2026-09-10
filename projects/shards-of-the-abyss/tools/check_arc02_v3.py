#!/usr/bin/env python3
"""Technical integrity only. Run from anywhere; never edits literary text."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
from urllib.parse import unquote

P = Path(__file__).resolve().parents[1]
R = P.parents[1]
BASE = 'db5550f7ff12acbb2da9d49b5f36ae70f0eb7c08'
BRANCH = 'arena/01a08101-workspace'
def git(*args):
    return subprocess.check_output(['git', *args], cwd=R)
def sha(data):
    return hashlib.sha256(data).hexdigest()
def stats(path):
    data = path.read_bytes(); text = data.decode('utf-8')
    return dict(sha256=sha(data), characters=len(text), whitespace_words=len(text.split()), lines=len(text.splitlines()))
assert git('branch', '--show-current').decode().strip() == BRANCH
manifest = json.loads((P/'IMPORT.json').read_text())
for item in manifest['files']:
    assert sha((P/'book'/item['path']).read_bytes()) == item['sha256'], item['path']
assert len(manifest['files']) == 397
previous = {}
for n in range(1, 11):
    f = P/f'drafts/ch-{n:02}/ch-{n:02}-v2.md'
    assert f.read_bytes() == git('show', f'{BASE}:{f.relative_to(R)}'), f
    previous[str(f.relative_to(P))] = sha(f.read_bytes())
a = (P/'book/03-manuscript/arc-01/ch-01.md').read_bytes().splitlines(keepends=True)[:111]
b = (P/'drafts/ch-01/ch-01-v2.md').read_bytes().splitlines(keepends=True)[:111]
assert a == b
chapters = [P/f'drafts/ch-{n:02}/ch-{n:02}-v{2 if n<8 else 3}.md' for n in range(6,11)]
combined = P/'drafts/arc-02/arc-02-v3.md'
assert combined.read_text() == '\n\n'.join(f.read_text().rstrip() for f in chapters)+'\n'
for f in chapters[2:]:
    text = f.read_text()
    assert text.startswith(f'# Глава {int(f.parent.name[-2:])}\n\n')
    assert text.endswith('\n') and '\ufffd' not in text and '\x00' not in text
    assert not re.search(r'(?m)[ \t]+$', text)
    for line in text.splitlines():
        assert line.count('*') % 2 == 0, (f, line)
    for stale in ('Тобер', 'Сухой Брод', 'Союз Свободных Дверей', 'Арка, у которой меня посадили', 'Я моргнула.*'):
        assert stale not in text, (f, stale)
pairs = json.loads((P/'review/arc-02-v3-before-after.json').read_text())
assert len(pairs) == 6
counts = {}
verified = []
for pair in pairs:
    counts[pair['after_path']] = counts.get(pair['after_path'], 0)+1
    result = {'title': pair['title']}
    for side in ('before', 'after'):
        text = (P/pair[side+'_path']).read_text(); quote = pair[side]
        assert text.count(quote) == 1, (pair['title'], side)
        at = text.index(quote); first = text[:at].count('\n')+1
        result[side] = {'path': pair[side+'_path'], 'exact_contiguous': True,
                        'lines': [first, first+quote.count('\n')], 'sha256': sha(quote.encode())}
    verified.append(result)
assert sorted(counts.values()) == [2, 2, 2]
links = 0
files = [R/x for x in ('README.md', 'NOW.md', 'AGENTS.md', 'ABOUT.md')]
files += [f for f in P.rglob('*.md') if 'book' not in f.relative_to(P).parts]
# The report below is itself linked from the worklog; its target is known.
report_path = P/'review/arc-02-v3-check.json'
for f in files:
    for link in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)', f.read_text()):
        if re.match(r'\w+://|mailto:|#', link): continue
        path = unquote(link.split('#')[0])
        if not path: continue
        target = (f.parent/path).resolve()
        assert target.exists() or target == report_path, (f, link)
        links += 1
report = {
    'scope': 'Technical preservation, exact excerpts, package, local links and formatting; not a literary or medical certificate.',
    'branch': BRANCH, 'comparison_baseline_commit': BASE,
    'imported_files_checked': 397, 'changed_or_missing_imported_files': [],
    'previous_ten_v2_unchanged': previous, 'protected_ch01_opening_lines_1_111_byte_identical': True,
    'chapters': {str(f.relative_to(P)): stats(f) for f in chapters},
    'reading_edition': {'path': str(combined.relative_to(P)), **stats(combined), 'chapter_bodies_exact': True},
    'comparisons': verified, 'local_markdown_links_checked': links,
    'formatting_checks_passed': True,
    'reading_boundary': 'All delivered 6–10 v2, all source 11, each new 8–10 v3 twice; final eight changes read locally. 12–16 only targeted.'
}
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
print(f'PASS: 397 imports, 10 v2 baselines, protected opening, 5 chapter bodies, 6 exact pairs, {links} local links.')
