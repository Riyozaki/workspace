"""Собирает таблицу «было → стало» из edits_*.py главы (без запуска правок)."""
import sys,re,pathlib,ast
d=pathlib.Path(sys.argv[1]); out=[]; total=0
for f in sorted(d.glob('edits_*.py')):
    src=f.read_text(encoding='utf-8')
    m=re.search(r'pairs\s*=\s*(\[.*?\n\])',src,re.S) or re.search(r'run\([A-Za-z_]+\s*,\s*(\[.*?\n\])\s*\)',src,re.S)
    if not m: out.append(f"\n## {f.name}: не разобран"); continue
    pairs=ast.literal_eval(m.group(1)); total+=len(pairs)
    out.append(f"\n## {f.name} ({len(pairs)})\n\n| # | было | стало |\n|---|---|---|")
    cl=lambda s: s.replace('\n',' ⏎ ').replace('|','\\|')
    for i,(a,b) in enumerate(pairs,1):
        out.append(f"| {i} | {cl(a)} | {cl(b) if b.strip() else '(снять)'} |")
print(f"Всего замен: {total}"); print("\n".join(out))
