"""Build a searchable, font-embedded reading PDF with live TOC and 35 bookmarks.
This is a reading proof, not a printer-specific PDF/X package.
Install requirements.txt in a virtual environment, then run this file.
"""
from pathlib import Path
import re,json,html
import pyphen
HYPHENATOR=pyphen.Pyphen(lang="ru_RU")
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER,TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import BaseDocTemplate,PageTemplate,Frame,Paragraph,PageBreak,Spacer,TableStyle
from reportlab.platypus.tableofcontents import TableOfContents

ED=Path(__file__).resolve().parents[1]
W,H=152*mm,229*mm
LEFT=21*mm; RIGHT=18*mm; TOP=20*mm; BOTTOM=19*mm
INK=colors.HexColor('#252220'); ACCENT=colors.HexColor('#704B40')
for suffix,name in [('', 'Book'),('-Italic','BookI'),('-Bold','BookB'),('-BoldItalic','BookBI')]:
    pdfmetrics.registerFont(TTFont(name,str(ED/'fonts'/f'DejaVuSerif{suffix}.ttf')))
pdfmetrics.registerFontFamily('Book',normal='Book',bold='BookB',italic='BookI',boldItalic='BookBI')
body=ParagraphStyle('Body',fontName='Book',fontSize=10.5,leading=14.3,alignment=TA_JUSTIFY,
    textColor=INK,firstLineIndent=5*mm,spaceAfter=0,spaceBefore=0,
    allowWidows=0,allowOrphans=0,hyphenationLang='ru_RU',embeddedHyphenation=1,
    splitLongWords=0,uriWasteReduce=0)
chapter=ParagraphStyle('Chapter',fontName='Book',fontSize=19,leading=25,
    alignment=TA_CENTER,spaceBefore=19*mm,spaceAfter=12*mm,keepWithNext=True,textColor=INK)
scene=ParagraphStyle('Scene',fontName='Book',fontSize=10,leading=15,alignment=TA_CENTER,
    spaceBefore=7,spaceAfter=7,keepWithNext=True,textColor=ACCENT)
title=ParagraphStyle('Title',fontName='Book',fontSize=30,leading=39,alignment=TA_CENTER,textColor=INK)
sub=ParagraphStyle('Sub',fontName='Book',fontSize=12,leading=19,alignment=TA_CENTER,textColor=ACCENT)
small=ParagraphStyle('Small',parent=sub,fontSize=8,leading=12,textColor=colors.HexColor('#68605a'))
tocstyle=ParagraphStyle('TOCEntry',fontName='Book',fontSize=9.6,leading=13,spaceBefore=0,spaceAfter=0,textColor=INK)

def markup(text):
    text=html.escape(text,quote=False)
    text=re.sub(r'[А-Яа-яЁё]{6,}',lambda m:HYPHENATOR.inserted(m.group(),hyphen='\u00ad'),text)
    text=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',text)
    text=re.sub(r'\*([^*]+)\*',r'<i>\1</i>',text)
    # Typographic glue only: the manuscript itself keeps ordinary spaces.
    text=re.sub(r'(?<!\w)([А-Яа-яЁё]{1,2}) (?=[А-Яа-яЁё«„“0-9])',lambda m:m.group(1)+'\u00a0',text)
    text=re.sub(r'^— ', '—\u00a0',text)
    return text

class BookDoc(BaseDocTemplate):
    def __init__(self,path):
        super().__init__(str(path),pagesize=(W,H),leftMargin=LEFT,rightMargin=RIGHT,
            topMargin=TOP,bottomMargin=BOTTOM,title='Осколки Бездны. Книга первая',
            author='',subject='Редакторская сборка 16 сентября 2026',pageCompression=1)
        self.chapter_starts={};self.current_chapter=None
        frame=Frame(LEFT,BOTTOM,W-LEFT-RIGHT,H-TOP-BOTTOM,id='body',leftPadding=0,
            rightPadding=0,topPadding=0,bottomPadding=0)
        self.addPageTemplates(PageTemplate(id='Book',frames=[frame],onPageEnd=self.furniture))
    def beforeDocument(self):
        self.chapter_starts={};self.current_chapter=None
    def afterFlowable(self,f):
        if hasattr(f,'chapter_number'):
            n=f.chapter_number;key=f'ch-{n}';self.current_chapter=n
            self.canv.bookmarkPage(key);self.canv.addOutlineEntry(f'Глава {n}',key,0)
            self.notify('TOCEntry',(0,f'Глава {n}',self.page-2,key))
            self.chapter_starts[n]=self.page
    def furniture(self,canvas,doc):
        if doc.page<=2 or self.current_chapter is None:return
        canvas.saveState();canvas.setFont('Book',7);canvas.setFillColor(colors.HexColor('#716960'))
        if self.chapter_starts.get(self.current_chapter)!=doc.page:
            label='ОСКОЛКИ БЕЗДНЫ' if doc.page%2==0 else f'ГЛАВА {self.current_chapter}'
            canvas.drawCentredString(W/2,H-11*mm,label)
        canvas.setFont('Book',8);canvas.drawCentredString(W/2,10*mm,str(doc.page-2))
        canvas.restoreState()

story=[Spacer(1,46*mm),Paragraph('ОСКОЛКИ<br/>БЕЗДНЫ',title),Spacer(1,10*mm),
       Paragraph('Книга первая',sub),Spacer(1,63*mm),
       Paragraph('Редакторская сборка<br/>16 сентября 2026',small),PageBreak(),
       Paragraph('Содержание',ParagraphStyle('TOCTitle',parent=chapter,spaceBefore=0,spaceAfter=9*mm))]
toc=TableOfContents(tableStyle=TableStyle([('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]));toc.levelStyles=[tocstyle];toc.dotsMinLevel=0
story.extend([toc,PageBreak()])
for n in range(1,36):
    if n>1:story.append(PageBreak())
    heading=Paragraph(f'Глава {n}',chapter);heading.chapter_number=n;story.append(heading)
    source=(ED/'chapters'/f'{n:02}.md').read_text();source=re.sub(r'^# Глава[^\n]*\n','',source).strip()
    for p in re.split(r'\n\s*\n',source):
        if p.strip() in ('***','* * *'):story.append(Paragraph('* * *',scene))
        elif p.strip():story.append(Paragraph(markup(p.strip()),body))
doc=BookDoc(ED/'shards-of-the-abyss-edited.pdf');doc.multiBuild(story,maxPasses=5)
(ED/'layout.json').write_text(json.dumps({'page_size_mm':[152,229],'font':'DejaVu Serif',
    'font_pt':10.5,'leading_pt':14.3,'body_box_pt':[LEFT,TOP,W-RIGHT,H-BOTTOM],
    'frontmatter_pages':2,'chapter_starts_pdf':doc.chapter_starts,'pages':doc.page},ensure_ascii=False,indent=2)+'\n')
print(f'PDF built: {doc.page} pages, {len(doc.chapter_starts)} chapter bookmarks.')
