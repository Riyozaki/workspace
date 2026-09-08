#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Редакторский линтер русского текста: типографика, повторы, согласование по мелочи.
Не про стиль (это style_guard), а про грамотность и опечатки."""
import re, sys, collections

def sentences(t):
    return re.split(r'(?<=[.!?…])\s+', t)

def check(path):
    t = open(path, encoding='utf-8').read()
    lines = t.split('\n')
    out = []
    def add(code, ln, msg, frag=''):
        out.append((code, ln, msg, frag.strip()[:160]))

    for i, ln in enumerate(lines, 1):
        if not ln.strip():
            continue
        # типографика
        if re.search(r'\s-\s', ln):
            add('DASH', i, 'дефис вместо тире', ln)
        if re.search(r'^\s*-\s', ln):
            add('DASH_DIALOG', i, 'реплика с дефисом вместо тире', ln)
        if '  ' in ln:
            add('DOUBLESPACE', i, 'двойной пробел', ln)
        if re.search(r'\s[,.;:!?]', ln):
            add('SPACE_PUNCT', i, 'пробел перед знаком', ln)
        if re.search(r'[,.;:!?][А-Яа-яЁё]', ln):
            add('NOSPACE_PUNCT', i, 'нет пробела после знака', ln)
        if '"' in ln or "''" in ln:
            add('QUOTES', i, 'прямые кавычки вместо «»', ln)
        if re.search(r'\.\.(?!\.)', ln) and '...' not in ln:
            add('DOTS2', i, 'две точки', ln)
        if re.search(r'\.{4,}', ln):
            add('DOTS4', i, 'четыре и больше точек', ln)
        if re.search(r'[а-яё]{2,}[A-Za-z]|[A-Za-z][а-яё]{2,}', ln):
            add('LATIN', i, 'латиница внутри слова', ln)
        # удвоенное слово
        for m in re.finditer(r'\b([А-Яа-яЁё]{3,})\s+\1\b', ln, re.I):
            add('DUP_WORD', i, 'слово подряд дважды: ' + m.group(1), ln)
        # запятая перед «что/который/потому что» — не проверяем автоматически, шумно
        # артефакт автозамены
        if re.search(r'\bэто,\s+было\b', ln):
            add('AUTOREPLACE', i, 'артефакт «это, было»', ln)
        if re.search(r'\bё\b', ln):
            pass
        # слипшиеся абзацы: реплика в середине абзаца прозы
        if not ln.startswith('—') and re.search(r'[а-яё]\.\s—\s[А-ЯЁ]', ln) is None and re.search(r'(?<![.!?…»,])\s—\s[А-ЯЁ][а-яё]+,?\s*—', ln):
            add('GLUED', i, 'возможно слипшийся абзац с репликой', ln)
        # повтор корня в пределах строки (грубо, по 6 первым буквам)
        words = re.findall(r'[А-Яа-яЁё]{7,}', ln.lower())
        c = collections.Counter(w[:6] for w in words)
        for stem, n in c.items():
            if n >= 3:
                add('STEM_REPEAT', i, f'корень «{stem}» {n} раза в абзаце', ln)
    return out

def main():
    total = collections.Counter()
    for p in sys.argv[1:]:
        res = check(p)
        if res:
            print(f'\n=== {p} ===')
            for code, ln, msg, frag in res:
                print(f'[{code}] {ln}: {msg}')
                if frag:
                    print('    ' + frag)
        for code, *_ in res:
            total[code] += 1
    print('\n--- итог ---')
    for k, v in total.most_common():
        print(f'{k}: {v}')

if __name__ == '__main__':
    main()
