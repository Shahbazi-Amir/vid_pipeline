#!/usr/bin/env python3
"""Generate right-aligned Persian Word files from approved reviewed.md."""
from pathlib import Path
import re
from docx import Document
from docx.shared import Cm,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from markdown_it import MarkdownIt

ROOT=Path('outputs/four-audio-final')
FONT_FA='Noto Naskh Arabic'
FONT_EN='Noto Sans'
NAVY=RGBColor(29,51,72)
TEAL=RGBColor(41,102,115)
DARK=RGBColor(35,43,51)
GRAY=RGBColor(106,118,128)
TITLES={
'01':'درس ۰۱ — فیزیولوژی سلول، اندامک‌ها و غشای سلولی',
'02':'درس ۰۲ — غشای سلولی، انتقال مواد و اسمز',
'03':'درس ۰۳ — کانال‌های یونی و پتانسیل استراحت غشا',
'04':'درس ۰۴ — پتانسیل عمل، هدایت عصبی و غلاف میلین',
}
def child(parent,name):
    o=parent.find(qn(name))
    if o is None:
        o=OxmlElement(name)
        parent.append(o)
    return o
def align(p,center=False):
    p.alignment=WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.RIGHT
    pr=p._p.get_or_add_pPr()
    for b in list(pr.findall(qn('w:bidi'))):pr.remove(b)
    child(pr,'w:jc').set(qn('w:val'),'center' if center else 'right')
def font(r,size=None,color=None,bold=None,italic=None,math=False):
    pr=r._r.get_or_add_rPr()
    f=child(pr,'w:rFonts')
    for k,v in [('ascii',FONT_EN),('hAnsi',FONT_EN),('eastAsia',FONT_FA),('cs',FONT_FA)]:
        f.set(qn('w:'+k),v)
    child(pr,'w:rtl').set(qn('w:val'),'0' if math else '1')
    child(pr,'w:lang').set(qn('w:bidi'),'en-US' if math else 'fa-IR')
    if size:
        r.font.size=Pt(size)
        child(pr,'w:szCs').set(qn('w:val'),str(round(size*2)))
    if color:r.font.color.rgb=color
    if bold is not None:r.bold=bold
    if italic is not None:r.italic=italic
def border(p,color='D5DEE2',size=5,space=7):
    b=child(child(p._p.get_or_add_pPr(),'w:pBdr'),'w:bottom')
    for k,v in [('val','single'),('sz',str(size)),('space',str(space)),('color',color)]:
        b.set(qn('w:'+k),v)
def style(d,name,size,color,bold=False,before=0,after=0,line=1.5,keep=False):
    s=d.styles.add_style(name,WD_STYLE_TYPE.PARAGRAPH)
    s.font.name=FONT_FA
    s.font.size=Pt(size)
    s.font.bold=bold
    s.font.color.rgb=color
    pf=s.paragraph_format
    pf.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    pf.space_before=Pt(before)
    pf.space_after=Pt(after)
    pf.line_spacing=line
    pf.keep_with_next=keep
    pr=s.element.get_or_add_pPr()
    for b in list(pr.findall(qn('w:bidi'))):pr.remove(b)
    child(pr,'w:jc').set(qn('w:val'),'right')
def inline(p,tokens):
    b=False
    i=False
    for t in tokens:
        typ=t.type
        if typ=='strong_open':b=True
        elif typ=='strong_close':b=False
        elif typ=='em_open':i=True
        elif typ=='em_close':i=False
        elif typ in ('text','code_inline','html_inline'):
            if not t.content or t.content.startswith('<'):continue
            r=p.add_run(t.content)
            font(r,bold=b,italic=i,color=TEAL if typ=='code_inline' else None)
        elif typ in ('softbreak','hardbreak'):
            font(p.add_run('\n'))
def run(n):
    path=ROOT/n/'reviewed.md'
    md=path.read_text(encoding='utf-8')
    if '<div dir="rtl"' in md:
        md=md.split('<div dir="rtl"',1)[1]
        md=md.split('>',1)[1].rsplit('</div>',1)[0]
    md=md.strip()
    assert len(md)>8000,(n,len(md))
    assert 'https://' not in md and 'http://' not in md
    if n=='03':
        # The reviewed Markdown contains two display LaTeX equations.
        # Match the accepted Word rendering rather than printing LaTeX control characters.
        for equation in ('V_m = V_in − V_out',
                         'E_ion ≈ (61.5 mV / z) × log₁₀([ion]_out / [ion]_in)'):
            begin=md.find(r'\[')
            end=md.find(r'\]',begin)
            assert begin>=0 and end>begin,(n,equation)
            md=md[:begin]+equation+md[end+2:]
        md=md.replace(r'\(V_m\)','Vₘ').replace(r'\(z\)','z')
    tokens=MarkdownIt('commonmark',{'html':True}).enable('table').parse(md)
    d=Document()
    sec=d.sections[0]
    sec.page_width=Cm(21)
    sec.page_height=Cm(29.7)
    sec.left_margin=Cm(2.2)
    sec.right_margin=Cm(2.3)
    sec.top_margin=Cm(2.45)
    sec.bottom_margin=Cm(2.25)
    sec.header_distance=Cm(1.0)
    sec.footer_distance=Cm(1.15)
    norm=d.styles['Normal']
    norm.font.name=FONT_FA
    norm.font.size=Pt(11.2)
    norm.font.color.rgb=DARK
    pf=norm.paragraph_format
    pf.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    pf.space_after=Pt(8)
    pf.line_spacing=1.55
    pr=norm.element.get_or_add_pPr()
    for b in list(pr.findall(qn('w:bidi'))):pr.remove(b)
    child(pr,'w:jc').set(qn('w:val'),'right')
    style(d,'Lesson title',19.3,NAVY,True,after=13,line=1.55,keep=True)
    style(d,'Lesson heading',14.1,NAVY,True,before=17,after=9,line=1.45,keep=True)
    style(d,'Lesson subheading',12.1,TEAL,True,before=11,after=6,line=1.4,keep=True)
    style(d,'Lesson list',11.1,DARK,after=5,line=1.55)
    style(d,'Lesson equation',11,DARK,before=3,after=9,line=1.4)
    h=sec.header.paragraphs[0]
    align(h)
    font(h.add_run(TITLES[n].split(' — ',1)[1]),size=8.4,color=GRAY)
    border(h,color='DBE5E9',size=3,space=4)
    foot=sec.footer.paragraphs[0]
    align(foot,center=True)
    font(foot.add_run('صفحه '),size=9,color=GRAY)
    f=OxmlElement('w:fldSimple')
    f.set(qn('w:instr'),'PAGE')
    foot._p.append(f)
    font(foot.add_run('  |  درس '+n),size=9,color=GRAY)
    p=d.add_paragraph(style='Lesson title')
    align(p)
    font(p.add_run(TITLES[n]),size=19.3,color=NAVY,bold=True)
    border(p,color='6B9A9D',size=12,space=8)
    lvl=0
    listing=False
    table=None
    row=None
    j=0
    sections=0
    for t in tokens:
        ty=t.type
        if ty=='heading_open':
            lvl=int(t.tag[1:])
            continue
        if ty=='heading_close':
            lvl=0
            continue
        if ty in ('bullet_list_open','ordered_list_open'):
            listing=True
            continue
        if ty in ('bullet_list_close','ordered_list_close'):
            listing=False
            continue
        if ty=='table_open':
            table=d.add_table(rows=0,cols=4)
            table.style='Table Grid'
            continue
        if ty=='table_close':
            table=None
            continue
        if ty=='tr_open':
            row=table.add_row()
            j=0
            continue
        if ty=='html_block':
            continue
        if ty!='inline' or not t.content.strip():
            continue
        if table is not None:
            if j>=4:continue
            c=row.cells[j]
            j+=1
            p=c.paragraphs[0]
            align(p)
            inline(p,t.children or [])
            c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for r in p.runs:font(r,size=9.3)
            continue
        if lvl:
            if lvl==1:continue
            p=d.add_paragraph(style='Lesson heading' if lvl==2 else 'Lesson subheading')
            align(p)
            inline(p,t.children or [])
            if lvl==2:
                border(p,color='E4E9ED',size=4,space=5)
                sections+=1
        elif listing:
            p=d.add_paragraph(style='Lesson list')
            align(p)
            p.paragraph_format.right_indent=Cm(0.65)
            p.paragraph_format.first_line_indent=Cm(-0.45)
            font(p.add_run('•  '),size=11.5,bold=True,color=TEAL)
            inline(p,t.children or [])
        else:
            math=t.content.strip().startswith('V_m =') or t.content.strip().startswith('E_ion')
            p=d.add_paragraph(style='Lesson equation' if math else 'Normal')
            align(p,center=math)
            inline(p,t.children or [])
    d.core_properties.title=TITLES[n]
    d.core_properties.author=''
    d.core_properties.last_modified_by=''
    output=ROOT/n/'final.docx'
    d.save(output)
    test=Document(output)
    allp=test.paragraphs+[p for tb in test.tables for row in tb.rows for c in row.cells for p in c.paragraphs]
    for p in allp:
        pr=p._p.get_or_add_pPr()
        jc=pr.find(qn('w:jc'))
        assert jc is not None and jc.get(qn('w:val')) in ('right','center')
        assert pr.find(qn('w:bidi')) is None
    assert sections>=16,(n,sections)
    print(n,sections,len(allp),output.stat().st_size)
for n in ('01','02','03','04'):run(n)
