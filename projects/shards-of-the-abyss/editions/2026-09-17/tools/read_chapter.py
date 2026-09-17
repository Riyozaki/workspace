"""Bounded reader; never records reading coverage automatically.
Usage: python read_chapter.py CHAPTER PART [--revised]
Default: immutable published 16.09 edition, paragraph indices used by changes.json.
--revised: actual generated 17.09 chapter; indices may differ after deletions.
"""
from pathlib import Path
import sys,re
ED=Path(__file__).resolve().parents[1]
base=ED if '--revised' in sys.argv else ED.parent/'2026-09-16'
n=int(sys.argv[1]);k=int(sys.argv[2])
path=base/'chapters'/f'{n:02}.md'
paras=re.split(r'\n\s*\n',path.read_text().strip())
parts=[];part=[];size=0
for i,p in enumerate(paras):
    if size+len(p)>14500 and part:parts.append(part);part=[];size=0
    part.append((i,p));size+=len(p)+20
if part:parts.append(part)
assert 1<=k<=len(parts)
print(f'SOURCE {path}\nCHAPTER {n}; PART {k}/{len(parts)}; paragraphs {parts[k-1][0][0]}–{parts[k-1][-1][0]}; total paragraphs {len(paras)}')
for i,p in parts[k-1]:print(f'[{i}] {p}\n')
