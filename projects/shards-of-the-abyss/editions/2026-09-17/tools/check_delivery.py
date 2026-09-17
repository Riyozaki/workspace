"""Verify release hashes, immutable comparison base, ledger replay and 70 exact pairs."""
from pathlib import Path
import collections,hashlib,json,re
ED=Path(__file__).resolve().parents[1];BASE=ED.parent/'2026-09-16'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
pars=lambda p:re.split(r'\n\s*\n',p.read_text().strip())
manifest=json.loads((ED/'manifest.json').read_text())
log=json.loads((ED/'changes.json').read_text())
assert manifest['operations']==len(log)
assert len(manifest['chapters'])==35
base={n:pars(BASE/'chapters'/f'{n:02}.md') for n in range(1,36)}
replay={n:a[:] for n,a in base.items()}
for x in log:
 n,i=x['chapter'],x['paragraph'];assert replay[n][i]==x['before'];replay[n][i]=x['after']
for e in manifest['chapters']:
 n=e['chapter'];assert sha(BASE/'chapters'/f'{n:02}.md')==e['source_sha256']
 assert sha(ED/e['file'])==e['output_sha256']
 assert (ED/e['file']).read_text()=='\n\n'.join(x for x in replay[n] if x)+'\n'
for name,digest in manifest['outputs'].items():assert sha(ED/name)==digest,name
assert 'shards-of-the-abyss-edited.pdf' in manifest['outputs']
pairs=json.loads((ED/'before-after.json').read_text());assert len(pairs)==70
assert collections.Counter(x['chapter'] for x in pairs)=={n:2 for n in range(1,36)}
for x in pairs:
 n,i=x['chapter'],x['source_paragraph'];assert base[n][i]==x['before']
 assert replay[n][i]==x['after'] and x['before']!=x['after']
 assert x['after'] in (ED/'chapters'/f'{n:02}.md').read_text()
docx=json.loads((ED/'docx-qa.json').read_text());pdf=json.loads((ED/'pdf-qa.json').read_text())
assert docx['status']=='pass' and docx['docx_sha256']==sha(ED/'shards-of-the-abyss.docx')
assert pdf['letter_sequence_equal'] and pdf['nonwhitespace_text_equal_except_hyphens_and_asterisks']
assert not pdf['blank_pages'] and not pdf['outside_page']
result={'status':'pass','chapters':35,'operations':len(log),'distinct_source_paragraphs':len({(x['chapter'],x['paragraph']) for x in log}),'exact_pairs':70,'output_hashes_equal':True,'ledger_replay_equal':True,'published_base_hashes_equal':True,'scope':'Mechanical integrity only; not independent literary proofreading or office pagination.'}
(ED/'delivery-qa.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
