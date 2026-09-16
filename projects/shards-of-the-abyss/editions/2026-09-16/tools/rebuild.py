"""Replay reviewed paragraph edits against hash-locked sources. No fuzzy replacement.
Run from anywhere: python path/to/rebuild.py
Archives and the uploaded candidate are never written.
"""
import hashlib,json,re
from pathlib import Path
EDITION=Path(__file__).resolve().parents[1]
ROOT=next(p for p in EDITION.parents if (p/'.git').is_dir())
manifest=json.loads((EDITION/'manifest.json').read_text())
data={}
for entry in manifest['chapters']:
    source=ROOT/entry['source'];raw=source.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==entry['source_sha256'],f'Source changed: {source}'
    text=raw.decode('utf-8');n=entry['chapter']
    if source.name=='book-full-2026-09-15.md':
        heads=list(re.finditer(r'^# Глава (\d+)\s*$',text,re.M))
        h=heads[n-1];text=text[h.end():heads[n].start() if n<35 else len(text)]
    else:text=re.sub(r'^# Глава[^\n]*\n','',text)
    data[n]=[p.strip() for p in re.split(r'\n\s*\n',text.strip()) if p.strip() and p.strip()!='---']
for e in json.loads((EDITION/'editorial-changes.json').read_text()):
    p=data[e['chapter']];i=e['paragraph']
    assert p[i]==e['before'],f"Edit mismatch: {e['chapter']}:{i}"
    p[i]=e['after']
texts=[]
for e in manifest['chapters']:
    n=e['chapter'];text=f'# Глава {n}\n\n'+'\n\n'.join(p for p in data[n] if p)+'\n'
    target=EDITION/e['file']
    if target.exists() and target.read_text()!=text:
        raise SystemExit(f'Output differs from recipe: {target}. Preserve your edits before regenerating.')
    target.write_text(text)
    texts.append(text)
anthology='# Осколки Бездны\n\nКнига первая\n\n'+'\n'.join(texts)
target=EDITION/'book-edited.md'
if target.exists() and target.read_text()!=anthology:
    raise SystemExit('Anthology differs from recipe. Preserve your edits before regenerating.')
target.write_text(anthology)
print('Rebuilt 35 chapters and book-edited.md; all input hashes and edit assertions passed.')
