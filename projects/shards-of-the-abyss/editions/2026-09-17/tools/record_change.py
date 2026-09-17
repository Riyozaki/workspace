"""Import change(chapter, base_paragraph_index, new_text, reason); never edits source chapters.
Appends one asserted replacement to changes.json. Rebuild afterward.
"""
import json,re,sys
from pathlib import Path
ED=Path(__file__).resolve().parents[1]; BASE=ED.parent/'2026-09-16'
def change(n,i,new,reason):
 path=ED/'changes.json';log=json.loads(path.read_text()) if path.exists() else []
 pars=re.split(r'\n\s*\n',(BASE/'chapters'/f'{n:02}.md').read_text().strip())
 for x in log:
  if x['chapter']==n:assert pars[x['paragraph']]==x['before'];pars[x['paragraph']]=x['after']
 old=pars[i];assert old!=new
 log.append(dict(chapter=n,paragraph=i,before=old,after=new,reason=reason));path.write_text(json.dumps(log,ensure_ascii=False,indent=2)+'\n')
