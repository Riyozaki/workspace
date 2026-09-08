#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
voice_drift.py — детектор ухода от авторского голоса.

Проверяет то, чего не проверяли style_guard.py и tics.py:
  1. стерильность    — дефицит хеджей/маркеров/вопросов (главный ИИ-маркер)
  2. счётные тики    — «третий раз», «последние три дня»
  3. усыхание речи   — пинг-понг, короткие реплики, тощий абзац
  4. дефицит обрыва  — многоточие как эталонный приём автора
  5. симметрия       — «не X, а Y», анафора соседних реплик

Нормы измерены по 32 главам (272 618 слов), см. 02-writing-system/SKILL-writing-craft.md

ВАЖНО: строка '---' в главах 11+ — разрыв сцены, НЕ frontmatter.
Не вырезать её парами: это съедает половину текста.

Использование:
    python3 scripts/voice_drift.py 03-manuscript/arc-05/ch-25.md
    python3 scripts/voice_drift.py --all
    python3 scripts/voice_drift.py --all --trend
"""

import re
import sys
import glob
import statistics

WORD = r'[А-Яа-яЁёA-Za-z0-9-]+'

HEDGE = r'\b(кажется|казалось|будто|как будто|возможно|может быть|наверное|вроде|похоже|словно|по-моему|что ли)\b'
MARKER = r'\b(знаешь|знаете|понимаешь|понимаете|слушай|слушайте|в общем|короче|эй|поверь|поверьте|видишь|видите|пойми|поймите|вообще-то|то есть|скорее)\b'
ELLIPSIS = r'\.\.\.|…'

NUMERAL = (r'\b(?:один|одна|одно|два|две|три|четыре|пять|шесть|семь|восемь|девять|десять|'
           r'одиннадцать|двенадцать|тринадцать|четырнадцать|пятнадцать|двадцать|тридцать|'
           r'сорок|пятьдесят|сто|двести|тысяч\w*|\d+)\b')
ORDINAL = (r'\b(?:перв|втор|трет|четвёрт|четверт|пят|шест|седьм|восьм|девят|десят)'
           r'(?:ый|ий|ая|ое|ые|ого|ой|их|ым|ую|им|ом|ему|ыми)\b')
# один паттерн вместо трёх пересекающихся: «второй раз» ловился и NTH_TIME, и NTH_PERIOD
NTH_COUNTER = (r'\b(?:во|в|на)?\s?(?:втор|трет|четвёрт|пят|шест|десят)\w*\s+'
               r'(?:раз|год|месяц|день|неделю|сутки)\b')
LAST_N = (r'\b(?:последни[еийюя]\w*)\s+'
          r'(?:два|три|четыре|пять|шесть|семь|восемь|девять|десять|\d+)\s')

NOT_X_BUT_Y = r'\bне [^,.!?;\n]{1,30}, а (?:просто |только |скорее |вовсе )?[^,.!?;\n]{1,30}'
NOT_SO_MUCH = r'не столько[^.!?\n]{1,60}сколько'
# «Это была не вся правда» — законный ход автора, не симметрия. Не ловим.

REALISED = r'\b(?:понял|поняла|осознал|осознала|сообразил|сообразила)\b'

# нормы: (ключ, человекочитаемое, норма, блокер, направление)
#   direction 'max' — превышение плохо; 'min' — нехватка плохо
NORMS = [
    ('hedge_per1k',   'хеджи (кажется/вроде)',      0.80, 0.60, 'min'),
    ('marker_per1k',  'маркеры речи (ну/знаешь)',   1.40, 0.85, 'min'),
    ('ell_dial_per1k','многоточие-обрыв в репликах', 2.0, 0.5, 'min'),
    ('num_per1k',     'числительные',              20.0, 26.0, 'max'),
    ('ord_per1k',     'порядковые',                10.0, 14.0, 'max'),
    ('nth_per1k',     'счётчики (N-й раз/год) /1k', 1.7,  2.5, 'max'),
    ('words_per_para','слов на абзац',             10.5,  9.5, 'min'),
    ('dialogue_share','доля реплик, %',            20.0, 12.0, 'min'),
    ('median_reply',  'медиана реплики, слов',      3.0,  2.5, 'min'),
    ('short_reply_pc','реплик <=3 слов, %',        60.0, 70.0, 'max'),
    ('pingpong_per10k','пинг-понг серий /10k',     15.0, 25.0, 'max'),
    ('anaphora_per10k','анафора реплик /10k',       6.0, 12.0, 'max'),
    ('symmetry_total','симметрия (не X а Y)',       0.0,  1.0, 'max'),
]

# к какой оси относится показатель (для правила тревоги по двум осям)
AXIS = {
    'hedge_per1k': 'стерильность', 'marker_per1k': 'стерильность',
    'ell_dial_per1k': 'обрыв',
    'num_per1k': 'тики', 'ord_per1k': 'тики', 'nth_per1k': 'тики',
    'words_per_para': 'ритм', 'dialogue_share': 'ритм',
    'median_reply': 'ритм', 'short_reply_pc': 'ритм', 'pingpong_per10k': 'ритм',
    'anaphora_per10k': 'симметрия', 'symmetry_total': 'симметрия',
}


def _nondup(text, patterns):
    """Считает совпадения нескольких паттернов без двойного учёта одного места."""
    spans = []
    for p in patterns:
        for m in re.finditer(p, text, re.I):
            if not any(a <= m.start() < b for a, b in spans):
                spans.append((m.start(), m.end()))
    return len(spans)


def nw(text):
    return len(re.findall(WORD, text))


def is_reply(line):
    return line.strip().startswith('—')


def reply_core(line):
    """Реплика без авторской атрибуции после ' — '."""
    return re.split(r'\s+—\s+', line.strip().lstrip('—').strip())[0]


def analyse(text):
    total_words = nw(text)
    if not total_words:
        return None

    lines = [l.strip() for l in text.split('\n') if l.strip() and l.strip() != '---']
    body = [l for l in lines if not l.startswith('#')]

    replies = [l for l in body if is_reply(l)]
    narrative = '\n'.join(l for l in body if not is_reply(l))
    dialogue = '\n'.join(replies)
    dial_words = nw(dialogue) or 1

    reply_lens = [nw(reply_core(r)) for r in replies]
    reply_lens = [n for n in reply_lens if n]

    paras = [p for p in re.split(r'\n\s*\n', text)
             if p.strip() and not p.strip().startswith('#') and p.strip() != '---']

    # диалоговые блоки: реплики, разделённые не более чем одной строкой нарратива
    blocks, seq, gap = [], [], 0
    for l in body:
        if is_reply(l):
            seq.append(l)
            gap = 0
        else:
            gap += 1
            if gap > 1 and seq:
                blocks.append(seq)
                seq = []
    if seq:
        blocks.append(seq)

    pingpong = 0
    anaphora = 0
    for b in blocks:
        lens = [nw(reply_core(x)) for x in b]
        run = 0
        for n in lens:
            if 0 < n <= 4:
                run += 1
                if run >= 4:
                    pingpong += 1
                    run = 0
            else:
                run = 0
        for a, c in zip(b, b[1:]):
            wa = [w.lower().strip('.,!?…«»—:;') for w in reply_core(a).split()][:2]
            wb = [w.lower().strip('.,!?…«»—:;') for w in reply_core(c).split()][:2]
            if len(wa) == 2 and wa == wb:
                anaphora += 1

    def cnt(pat, where=text):
        return len(re.findall(pat, where, re.I))

    m = {
        'words': total_words,
        'hedge_per1k': cnt(HEDGE) / total_words * 1000,
        'marker_per1k': cnt(MARKER) / total_words * 1000,
        'ell_dial_per1k': cnt(ELLIPSIS, dialogue) / dial_words * 1000,
        'num_per1k': cnt(NUMERAL) / total_words * 1000,
        'ord_per1k': cnt(ORDINAL) / total_words * 1000,
        'nth_per1k': _nondup(text, (NTH_COUNTER, LAST_N)) / total_words * 1000,
        'words_per_para': total_words / max(len(paras), 1),
        'dialogue_share': nw(dialogue) / total_words * 100,
        'median_reply': statistics.median(reply_lens) if reply_lens else 0.0,
        'short_reply_pc': (sum(1 for n in reply_lens if n <= 3) / len(reply_lens) * 100)
                          if reply_lens else 0.0,
        'pingpong_per10k': pingpong / total_words * 10000,
        'anaphora_per10k': anaphora / total_words * 10000,
        'symmetry_total': cnt(NOT_X_BUT_Y) + cnt(NOT_SO_MUCH),
        'realised_endings': cnt(REALISED),
        'scenes': len(re.findall(r'^---\s*$', text, re.M)) + 1,
        'reply_count': len(reply_lens),
    }
    return m


# нормы, применимые только к главам с диалогом
DIALOGUE_KEYS = {'ell_dial_per1k', 'dialogue_share', 'median_reply',
                 'short_reply_pc', 'pingpong_per10k', 'anaphora_per10k'}


def verdict(m):
    """Возвращает (список нарушений, оси с жёстким пробоем).

    Тревога считается ТОЛЬКО по осям с BLOCK. Иначе эталонная глава 1,
    у которой четыре оси в мягком отклонении, получала бы «переписать».
    Мягкое отклонение — заметка, а не долг.
    """
    issues = []
    axes = set()
    # глава без диалога (сон, письмо, соло-эпизод) — не мерить речевыми нормами
    no_dialogue = m['reply_count'] < 15
    for key, label, norm, block, direction in NORMS:
        if no_dialogue and key in DIALOGUE_KEYS:
            continue
        v = m[key]
        hard = v > block if direction == 'max' else v < block
        soft = v > norm if direction == 'max' else v < norm
        if hard:
            issues.append(('BLOCK', label, v, norm))
            axes.add(AXIS[key])
        elif soft:
            issues.append(('WARN', label, v, norm))
    return issues, axes


def report(path, m):
    issues, axes = verdict(m)
    print(f"\n=== {path} ===")
    print(f"слов {m['words']}  сцен {m['scenes']}  "
          f"реплик {m['dialogue_share']:.0f}%  абзац {m['words_per_para']:.1f} сл.")

    if m['reply_count'] < 15:
        print("  (глава без диалога — речевые нормы не применяются)")
    if not issues:
        print("  чисто")
    for level, label, v, norm in issues:
        mark = '!!' if level == 'BLOCK' else ' ·'
        print(f"  {mark} {label:<28} {v:>7.1f}   норма {norm}")

    if m['realised_endings']:
        print(f"   · «понял/осознал» в тексте: {m['realised_endings']} "
              f"(проверить финалы сцен вручную)")

    n = len(axes)
    if n >= 3:
        print(f"  ТРЕВОГА по {n} осям ({', '.join(sorted(axes))}) — главу переписать")
    elif n == 2:
        print(f"  ТРЕВОГА по 2 осям ({', '.join(sorted(axes))}) — долг закрыть до следующей главы")
    elif n == 1:
        print(f"  одна ось ({list(axes)[0]}) — заметка")
    return len(axes)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    flags = {a for a in sys.argv[1:] if a.startswith('--')}

    if '--all' in flags or not args:
        files = sorted(glob.glob('03-manuscript/arc-*/ch-*.md'),
                       key=lambda p: int(re.search(r'ch-(\d+)', p).group(1)))
    else:
        files = args

    if '--trend' in flags:
        print(f"{'глава':<10}{'слов':>7}{'сл/абз':>8}{'%репл':>7}"
              f"{'медиана':>9}{'пинг/10k':>10}{'мтч/1k':>8}")
        by_arc = {}
        for f in files:
            m = analyse(open(f, encoding='utf-8').read())
            if not m:
                continue
            ch = int(re.search(r'ch-(\d+)', f).group(1))
            arc = ('arc-01' if ch <= 5 else 'arc-02' if ch <= 10 else
                   'arc-03' if ch <= 14 else 'arc-04' if ch <= 21 else 'arc-05')
            by_arc.setdefault(arc, []).append(m)
            print(f"ch-{ch:02d}{'':<5}{m['words']:>7}{m['words_per_para']:>8.1f}"
                  f"{m['dialogue_share']:>6.0f}%{m['median_reply']:>9.1f}"
                  f"{m['pingpong_per10k']:>10.1f}{m['ell_dial_per1k']:>8.2f}")
        print(f"\n{'арка':<10}{'глав':>5}{'ср.объём':>10}{'сл/абз':>8}"
              f"{'%репл':>7}{'медиана':>9}{'пинг/10k':>10}")
        for arc in sorted(by_arc):
            d = by_arc[arc]
            print(f"{arc:<10}{len(d):>5}"
                  f"{statistics.mean(x['words'] for x in d):>10.0f}"
                  f"{statistics.mean(x['words_per_para'] for x in d):>8.1f}"
                  f"{statistics.mean(x['dialogue_share'] for x in d):>6.0f}%"
                  f"{statistics.mean(x['median_reply'] for x in d):>9.1f}"
                  f"{statistics.mean(x['pingpong_per10k'] for x in d):>10.1f}")
        return 0

    worst = 0
    for f in files:
        m = analyse(open(f, encoding='utf-8').read())
        if m:
            worst = max(worst, report(f, m))
    print()
    return 1 if worst >= 2 else 0


if __name__ == '__main__':
    sys.exit(main())
