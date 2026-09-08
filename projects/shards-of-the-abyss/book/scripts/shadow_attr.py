#!/usr/bin/env python3
"""Единое правило атрибуции Тени.

Установлено проверкой: курсивом в книге говорит только Тень. Из её реплик
1549 уже идут без атрибуции, и ещё 1442 тащат за собой «— сказала она».
Одно и то же оформление в двух видах — не приём, а недосмотр.

Правило:
  * голая атрибуция «— сказала она/Тень» при курсивной реплике снимается;
  * первая реплика главы остаётся нетронутой — якорь голоса;
  * атрибуция с модификатором (наречие, деепричастие, придаточное) остаётся:
    она сообщает не «кто», а «как»;
  * прочие глаголы (согласилась, повторила, поправила) остаются: это действие;
  * «сказала та, что внутри» и «сказал голос» остаются: это не атрибуция,
    а способ называния, который меняется по ходу книги.

Запуск:
    python3 scripts/shadow_attr.py            # вхолостую
    python3 scripts/shadow_attr.py --apply    # внести правки
    python3 scripts/shadow_attr.py --verbose  # с примерами
"""
import re
import sys
import glob

# Голая атрибуция в конце курсивной реплики: *Текст,* — сказала она.
RE_END = re.compile(r'^(\*[^*]+?)([,?!])(\*) — сказала (?:она|Тень)\.$')
# Голая атрибуция между двумя курсивными кусками.
RE_MID = re.compile(r'^(\*[^*]+?)([,?!])\* — сказала (?:она|Тень)\. — \*([^*]+\*)$')

# Файлы, где курсив принадлежит не только Тени.
SKIP_FILES = set()


def merge(head, punct, tail):
    """Склеить два куска реплики, сохранив пунктуацию и регистр."""
    end = '.' if punct == ',' else punct
    if not tail:
        return head + end
    first = tail[0]
    # После вопроса или восклицания второй кусок начинается как новая фраза.
    return head + end + ' ' + tail


def process(path, apply=False):
    fname = path.split('/')[-1]
    if fname in SKIP_FILES:
        return 0, []
    text = open(path, encoding='utf-8').read()
    lines = text.split('\n')
    out = []
    anchored = False
    changed = 0
    report = []
    for i, line in enumerate(lines, 1):
        bare = (line.startswith('*')
                and ('— сказала она' in line or '— сказала Тень' in line))
        if bare and not anchored:
            anchored = True
            out.append(line)
            report.append((i, 'ЯКОРЬ', line[:60], '(оставлено)'))
            continue
        m = RE_END.match(line)
        if m:
            new = merge(m.group(1), m.group(2), '') + m.group(3)
            report.append((i, 'КОНЕЦ', line[:60], new[:60]))
            out.append(new)
            changed += 1
            continue
        m = RE_MID.match(line)
        if m:
            new = merge(m.group(1), m.group(2), m.group(3))
            report.append((i, 'СЕРЕД', line[:60], new[:60]))
            out.append(new)
            changed += 1
            continue
        out.append(line)
    if apply and changed:
        open(path, 'w', encoding='utf-8').write('\n'.join(out))
    return changed, report


def main():
    apply = '--apply' in sys.argv
    verbose = '--verbose' in sys.argv
    total = 0
    for path in sorted(glob.glob('03-manuscript/arc-0*/*.md')):
        n, rep = process(path, apply)
        total += n
        if n:
            print(f'{path.split("/")[-1]}: {n}')
        if verbose:
            for r in rep[:4]:
                print('   ', r[0], r[1], '|', r[2], '->', r[3])
    print('ИТОГО:', total, '(применено)' if apply else '(вхолостую)')


if __name__ == '__main__':
    main()
