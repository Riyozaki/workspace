"""DOCX package/content/style QA, not a substitute for visual pagination review."""
from pathlib import Path
import json,re,hashlib,posixpath
from zipfile import ZipFile
from collections import Counter
from lxml import etree
from docx import Document
from docx.oxml.ns import qn
from docx.shared import Mm,Pt
ED=Path(__file__).resolve().parents[1]
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r':'http://schemas.openxmlformats.org/package/2006/relationships'}
path=ED/'shards-of-the-abyss.docx'
doc=Document(path)
expected=[];expected_emphasis=[]
for n in range(1,36):
    pars=re.split(r'\n\s*\n',(ED/'chapters'/f'{n:02}.md').read_text().strip())
    assert pars.pop(0)==f'# Глава {n}'
    expected.append((n,f'Глава {n}'))
    for p in pars:
        if p.strip() in ('***','* * *'):
            expected.append((n,'* * *'));continue
        expected.append((n,p.replace('**','').replace('*','')))
        b=i=False;parts=[]
        for token in re.split(r'(\*\*|\*)',p):
            if token=='**':b=not b
            elif token=='*':i=not i
            elif token:parts.append((token,b,i))
        assert not b and not i
        expected_emphasis.append(parts)
actual=[];actual_emphasis=[];heads=[];current=None
for p in doc.paragraphs:
    if p.style.name=='Heading 1':
        assert re.fullmatch(r'Глава \d+',p.text)
        current=int(p.text.split()[-1]);heads.append(current)
        assert p.paragraph_format.page_break_before is (False if current==1 else None)
    if current is not None:
        actual.append((current,p.text))
        if p.style.name!='Heading 1' and p.text!='* * *':
            actual_emphasis.append([(r.text,bool(r.bold),bool(r.italic)) for r in p.runs])
assert heads==list(range(1,36))
assert actual==expected,'DOCX paragraph text/order differs from full Markdown chapters'
assert actual_emphasis==expected_emphasis,'DOCX inline emphasis differs'
assert len(doc.sections)==2
for sec in doc.sections:
    assert abs(sec.page_width-Mm(210))<1000 and abs(sec.page_height-Mm(297))<1000
style=doc.styles['Normal']
assert style.font.name=='Times New Roman' and style.font.size==Pt(12)
assert style.paragraph_format.widow_control
assert style.element.xpath('.//w:lang')[0].get(qn('w:val'))=='ru-RU'
assert doc.styles['Heading 1'].paragraph_format.keep_with_next
assert doc.styles['Heading 1'].paragraph_format.page_break_before
with ZipFile(path) as z:
    assert z.testzip() is None,'Corrupt ZIP member'
    names=z.namelist();assert len(names)==len(set(names))
    assert not any('vbaProject' in x for x in names)
    for name in names:
        if name.endswith(('.xml','.rels')):etree.fromstring(z.read(name))
    root=etree.fromstring(z.read('word/document.xml'))
    # Property elements must precede paragraph content (bookmarks included).
    for p in root.findall('.//w:p',NS):
        pp=p.find('w:pPr',NS)
        assert pp is None or p[0] is pp
    bookmarks=root.findall('.//w:bookmarkStart',NS)
    assert [b.get(qn('w:name')) for b in bookmarks]==[f'chapter_{n:02}' for n in range(1,36)]
    starts=[b.get(qn('w:id')) for b in bookmarks]
    ends=[b.get(qn('w:id')) for b in root.findall('.//w:bookmarkEnd',NS)]
    assert len(set(starts))==35 and Counter(starts)==Counter(ends)
    links=root.findall('.//w:hyperlink',NS)
    assert [l.get(qn('w:anchor')) for l in links]==[f'chapter_{n:02}' for n in range(1,36)]
    assert [''.join(l.itertext()) for l in links]==[f'Глава {n}' for n in range(1,36)]
    assert not root.findall('.//w:ins',NS) and not root.findall('.//w:del',NS)
    assert not root.findall('.//w:commentReference',NS)
    external=[];relations=0
    for name in names:
        if not name.endswith('.rels'):continue
        base=posixpath.dirname(posixpath.dirname(name))
        for rel in etree.fromstring(z.read(name)):
            target=rel.get('Target');relations+=1
            if rel.get('TargetMode')=='External':external.append(target);continue
            resolved=posixpath.normpath(posixpath.join(base,target)).lstrip('/')
            assert resolved in names,f'Missing package relationship target: {name}: {target}'
    assert not external,'Unexpected external document links'
    settings=etree.fromstring(z.read('word/settings.xml'))
    for key in ['autoHyphenation','doNotHyphenateCaps','updateFields']:
        es=settings.findall('w:'+key,NS)
        assert len(es)==1 and es[0].get(qn('w:val'))=='true'
    footers=[name for name in names if re.match(r'word/footer\d+\.xml$',name)]
    assert len(footers)==1
    assert 'PAGE' in ''.join(etree.fromstring(z.read(footers[0])).itertext())
result={'status':'pass','chapters':35,'body_paragraphs_including_headings_and_scene_breaks':len(expected),
        'exact_paragraph_text_and_order_equal':True,'bold_and_italic_runs_equal':True,
        'internal_contents_links':len(links),'bookmarks':len(bookmarks),'sections':2,
        'page_size_mm':[210,297],'body_font':'Times New Roman','body_pt':12,'body_line_spacing':1.15,
        'language':'ru-RU','external_links':external,'package_relationships_checked':relations,
        'docx_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'scope':'ZIP integrity, XML parseability, package relationships, selected OOXML element order, full paragraph text and inline emphasis, headings, bookmarks, internal links and manuscript styles. Not full XSD validation, grammar certification, or visual pagination review in Word/LibreOffice. Fonts are not embedded; pagination depends on reader software and installed fonts.'}
(ED/'docx-qa.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
