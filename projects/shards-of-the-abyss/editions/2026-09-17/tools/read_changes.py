"""Read actual generated revisions with adjacent paragraphs; no automatic journal.
Usage: python read_changes.py PART [LAST_CHAPTER] [FIRST_CHAPTER]
Verifies replay against each generated chapter, then merges contextual windows.
This supplements full reading; it is not a substitute for it.
"""
from pathlib import Path
import json,re,sys
ED=Path(__file__).resolve().parents[1];BASE=ED.parent/'2026-09-16'
log=json.loads((ED/'changes.json').read_text())
last=int(sys.argv[2]) if len(sys.argv)>2 else 35
first=int(sys.argv[3]) if len(sys.argv)>3 else 1
assert 1<=first<=last<=35
blocks=[]
for n in range(first,last+1):
    pars=re.split(r'\n\s*\n',(BASE/'chapters'/f'{n:02}.md').read_text().strip())
    changed=set()
    for x in log:
        if x['chapter']!=n:continue
        i=x['paragraph'];assert pars[i]==x['before'];pars[i]=x['after'];changed.add(i)
    expected='\n\n'.join(p for p in pars if p)+'\n'
    actual=(ED/'chapters'/f'{n:02}.md').read_text()
    assert actual==expected,f'Chapter {n} not synchronized to current ledger. Rebuild first.'
    rendered=re.split(r'\n\s*\n',actual.strip())
    spans={};cursor=0
    for old,p in enumerate(pars):
        length=len(re.split(r'\n\s*\n',p)) if p else 0
        spans[old]=(cursor,cursor+length);cursor+=length
    assert cursor==len(rendered)
    selected=set()
    for old in changed:
        start,end=spans[old]
        selected.update(range(max(0,start-1),min(len(rendered),end+1)))
    current=[];prev=-2
    for i in sorted(selected):
        if i!=prev+1 and current:
            blocks.append((n,current));current=[]
        current.append((i,rendered[i]));prev=i
    if current:blocks.append((n,current))
chunks=[];chunk=[];size=0
for n,block in blocks:
    # May split a large merged context at an actual paragraph boundary.
    for i,p in block:
        item=f'CHAPTER {n:02} / revised paragraph {i}\n{p}\n\n'
        if chunk and size+len(item)>14500:
            chunks.append(chunk);chunk=[];size=0
        chunk.append(item);size+=len(item)
if chunk:chunks.append(chunk)
k=int(sys.argv[1]);assert 1<=k<=len(chunks)
print(f'ACTUAL REVISED CONTEXTS {first}–{last}; PART {k}/{len(chunks)}; ledger operations {len(log)}')
print(''.join(chunks[k-1]))
