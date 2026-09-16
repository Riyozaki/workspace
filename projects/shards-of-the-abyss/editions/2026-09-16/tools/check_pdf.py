"""Bounded, explicit QA. Does not claim literary proofreading or PDF/X conformance."""
from pathlib import Path
import json,re,hashlib,collections
import pymupdf as fitz
ED=Path(__file__).resolve().parents[1]
layout=json.loads((ED/'layout.json').read_text());doc=fitz.open(ED/'shards-of-the-abyss-edited.pdf')
assert len(doc)==layout['pages']
assert len(doc.get_toc())==35
assert layout['chapter_starts_pdf']['1']==3,'Frontmatter pagination changed; adjust TOC numbering'
assert [x[1] for x in doc.get_toc()]==[f'Глава {i}' for i in range(1,36)]
bodybox=fitz.Rect(layout['body_box_pt'])
actual=[];overflow=[];used=set();blank=[]
for i,page in enumerate(doc):
    blocks=page.get_text('dict')['blocks']
    if not page.get_text().strip():blank.append(i+1)
    for block in blocks:
        for line in block.get('lines',[]):
            for span in line.get('spans',[]):
                used.add(span['font'])
                x0,y0,x1,y1=span['bbox']
                if x0<-.5 or y0<-.5 or x1>page.rect.width+.5 or y1>page.rect.height+.5:
                    overflow.append([i+1,span['text'],span['bbox']])
    if i>=2:
        text=page.get_text(clip=bodybox)
        text=re.sub(r'^Глава\s+\d+\s*','',text)
        actual.append(text)
source=[]
for i in range(1,36):
    t=(ED/'chapters'/f'{i:02}.md').read_text()
    assert t.startswith(f'# Глава {i}\n')
    assert '\ufffd' not in t
    source.append(re.sub(r'^# Глава[^\n]*\n','',t))
letters=lambda t:''.join(re.findall(r'[^\W\d_]',t,re.UNICODE))
a=letters(''.join(source));b=letters(''.join(actual));match=a==b
normalize=lambda t:re.sub(r'[\s*\u00ad\u2010\u2011-]','',t)
full_match=normalize(''.join(source))==normalize(''.join(actual))
first_difference=None
if not match:
    at=next((i for i,(x,y) in enumerate(zip(a,b)) if x!=y),min(len(a),len(b)))
    first_difference={'index':at,'source':a[max(0,at-70):at+120],'pdf':b[max(0,at-70):at+120]}
fonts=[]
seen=set()
for page in doc:
    for f in page.get_fonts():
        if f[0] in seen:continue
        seen.add(f[0]);name,ext,kind,data=doc.extract_font(f[0]);fonts.append({'name':name,'type':kind,'extension':ext,'embedded_bytes':len(data)})
result={'pages':len(doc),'bookmarks':len(doc.get_toc()),'toc_links':sum(len(doc[i].get_links()) for i in [0,1]),
 'blank_pages':blank,'outside_page':overflow,'source_letters':len(a),'pdf_letters':len(b),
 'nonwhitespace_text_equal_except_hyphens_and_asterisks':full_match,'letter_sequence_equal':match,'first_difference':first_difference,'used_fonts':sorted(used),'fonts':fonts,
 'scope':'Checks full Cyrillic/Latin letter sequence excluding page furniture; not punctuation equality, grammar, or literary quality.'}
(ED/'pdf-qa.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['fonts','scope']},ensure_ascii=False,indent=2))
assert not blank and not overflow
assert full_match,'Non-whitespace PDF text differs'
assert match,'PDF text differs from manuscript; inspect first_difference'
assert result['toc_links']>=35
for f in fonts:
    if 'DejaVu' in f['name']:assert f['embedded_bytes']>0
print('PDF QA PASS')
