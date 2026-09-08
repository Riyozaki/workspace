#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""continuity_check.py — детектор дефектов второго называния.

Ловит класс ошибок, невидимый и для style_guard.py (стиль), и для
voice_drift.py (голос), и для canon_check.py (реестр фактов): каждая
отдельная фраза написана правильно, но она противоречит другой фразе,
стоящей за тысячу строк отсюда.

Механизм дефекта один (см. SKILL-writing-craft.md §13): деталь,
называемая второй раз, не вспоминается, а сочиняется заново из того же
смыслового поля. Поэтому второй вариант всегда правдоподобен и почти
никогда не тождественен первому.

Проверки:
  POV_GENDER     род глагола при «я» в наррации (POV — женщина)
  NAME_VARIANTS  имена-двойники: Бондарная / Бочарная
  INDIRECT       кривая косвенная речь: «сказала, что извините»
  DURATION       разные сроки при одном имени: полтора года / четыре года
  NGRAM          формулы, повторяющиеся между главами
  GLUED          слитно-раздельно: «наощупь»
  REFLECTION     осмысление, осевшее ниже действия (показывает, где смотреть)
  UNSOURCED      точное время, которое POV нечем измерить (§3.3)
  TIMELINE       часы сцены подряд, для сверки глазом

Три последние — не приговор, а список для чтения: решает человек.

Использование:
    python3 scripts/continuity_check.py 03-manuscript/arc-01/ch-01.md
    python3 scripts/continuity_check.py 03-manuscript/arc-01/*.md
    python3 scripts/continuity_check.py --all
    python3 scripts/continuity_check.py --object пирог 03-manuscript/arc-01/*.md
"""

from __future__ import annotations

import argparse
import glob
import re
import sys
from collections import defaultdict
from pathlib import Path

WORD = r"[А-Яа-яЁёA-Za-z0-9-]+"

# ─────────────────────────────────────────────────────────────────────
# POV_GENDER
# ─────────────────────────────────────────────────────────────────────
# «я» + глагол прошедшего времени мужского рода. POV книги — женщина.
POV_VERB = re.compile(
    r"(?<![А-Яа-яЁё])я\s+"
    r"(?:не\s+|уже\s+|всё-таки\s+|тогда\s+|давно\s+|сразу\s+|чуть\s+не\s+|"
    r"едва\s+|только\s+что\s+|снова\s+|опять\s+|всё\s+ещё\s+)?"
    r"([а-яё]{4,}(?:л|лся))(?![а-яё])",
    re.IGNORECASE,
)
# существительные на -л, которые не глаголы
NOT_A_VERB = {
    "стол", "угол", "узел", "котёл", "ствол", "металл", "канал", "финал",
    "смысл", "числ", "престол", "осёл", "козёл", "орёл", "посёл", "приёл",
    "мускул", "модул", "купол", "вокзал", "квартал", "госпитал", "журнал",
    "материал", "мешал",  # «мешал» бывает и глаголом — оставлен в шуме
}


def check_pov_gender(paras: list[tuple[int, str]]) -> list[tuple[int, str]]:
    out = []
    for ln, p in paras:
        if is_speech(p):
            continue
        for m in POV_VERB.finditer(p):
            verb = m.group(1).lower()
            if verb in NOT_A_VERB:
                continue
            if verb.endswith("ла") or verb.endswith("лась"):
                continue
            out.append((ln, quote(p, m.start(), m.end())))
    return out


# ─────────────────────────────────────────────────────────────────────
# NAME_VARIANTS
# ─────────────────────────────────────────────────────────────────────
CAP_WORD = re.compile(r"(?<![.!?…»\"]\s)(?<!^)(?<!— )([А-ЯЁ][а-яё]{3,})")
ENDINGS = ("ыми", "ого", "ому", "ыми", "ая", "ой", "ую", "ые", "ых", "ым",
           "ов", "ев", "ин", "ом", "ем", "ах", "ям", "ья", "ье", "ий", "ый",
           "а", "у", "е", "ы", "и", "о", "ь", "я", "ю")


def stem(w: str) -> str:
    w = w.lower()
    for e in sorted(ENDINGS, key=len, reverse=True):
        if len(w) - len(e) >= 4 and w.endswith(e):
            return w[: -len(e)]
    return w


def lev(a: str, b: str) -> int:
    if abs(len(a) - len(b)) > 2:
        return 99
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


SENT_START = re.compile(r"(?:^|[.!?…:;»\"]\s+|—\s+|\*\s*)$")


def check_name_variants(files: dict[str, str]) -> list[str]:
    """Имена-двойники: Бондарная / Бочарная.

    Именем собственным считается только слово, которое хоть раз стоит с
    заглавной НЕ в начале фразы и ни разу не встречается со строчной.
    Иначе список забивают «Говори», «Восемь», «Больше».
    """
    seen: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    mid_cap: dict[str, int] = defaultdict(int)
    lower: dict[str, int] = defaultdict(int)

    for name, text in files.items():
        for i, line in enumerate(text.split("\n"), 1):
            for m in re.finditer(r"[А-ЯЁа-яё][а-яё]{3,}", line):
                w = m.group(0)
                s = stem(w)
                if w[0].islower():
                    lower[s] += 1
                    continue
                seen[s][w].append(f"{Path(name).stem}:{i}")
                if not SENT_START.search(line[: m.start()]):
                    mid_cap[s] += 1

    stems = sorted(s for s in seen if mid_cap[s] >= 1 and lower[s] == 0)
    out = []
    for i, s1 in enumerate(stems):
        for s2 in stems[i + 1:]:
            if len(s1) < 5 or len(s2) < 5:
                continue
            d = lev(s1, s2)
            if d == 0 or d > 2:
                continue
            if s1[:2] != s2[:2]:
                continue
            f1 = sum(len(v) for v in seen[s1].values())
            f2 = sum(len(v) for v in seen[s2].values())
            w1 = max(seen[s1], key=lambda k: len(seen[s1][k]))
            w2 = max(seen[s2], key=lambda k: len(seen[s2][k]))
            out.append(
                f"{w1} ({f1}×, {seen[s1][w1][0]}) ~ {w2} ({f2}×, {seen[s2][w2][0]})"
            )
    return out


# ─────────────────────────────────────────────────────────────────────
# INDIRECT
# ─────────────────────────────────────────────────────────────────────
SAID_THAT = re.compile(
    r"\b(сказал\w*|ответил\w*|спросил\w*|объяснил\w*|повторил\w*|бросил\w*)"
    r"[^.!?…\n]{0,20},\s+что\s+([^.!?…\n]{0,45})",
    re.IGNORECASE,
)
# слова, которые не переживают сдвига лица: вежливые формулы, императив,
# обращения, 1-е и 2-е лицо
FACE_LEAK = re.compile(
    r"\b(извини\w*|прости\w*|спасибо|пожалуйста|здравствуй\w*|прощай\w*|"
    r"мне|меня|тебе|тебя|вам|вас|нам|нас|мой|моя|моё|твой|твоя|ваш\w*|"
    r"я|ты|вы|мы)\b",
    re.IGNORECASE,
)
# «сказал, что нет» и «сказала, что я приду» — законно. Косвенная речь не
# принимает только вежливых формул и обращений: они существуют лишь в
# первом лице, и сдвиг лица их ломает.
HARD_LEAK = re.compile(
    r"\b(извини\w*|прости\w*|спасибо|пожалуйста|здравствуй\w*|прощай\w*|"
    r"будьте\s+добры|сделай\w*\s+одолжение)\b",
    re.IGNORECASE,
)


def check_indirect(paras: list[tuple[int, str]]) -> list[tuple[int, str]]:
    out = []
    for ln, p in paras:
        for m in SAID_THAT.finditer(p):
            tail = m.group(2)
            if HARD_LEAK.search(tail):
                out.append((ln, quote(p, m.start(), m.end())))
    return out


# ─────────────────────────────────────────────────────────────────────
# DURATION
# ─────────────────────────────────────────────────────────────────────
NUMWORD = (r"пол\w*|полтора|полутора|один|одна|два|две|три|четыре|пять|шесть|"
           r"семь|восемь|девять|десять|одиннадцать|двенадцать|пятнадцать|"
           r"двадцать|тридцать|сорок|\d+")
DURATION = re.compile(
    rf"\b({NUMWORD})\s+(лет|года|годы|год|месяц\w*|недел\w*|дн\w*|декад\w*)\b",
    re.IGNORECASE,
)
NAME = re.compile(r"(?<![А-ЯЁ])([А-ЯЁ][а-яё]{3,})(?![а-яё])")


def check_duration(files: dict[str, str], names: set[str]) -> dict[str, dict]:
    hits: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for fname, text in files.items():
        lines = text.split("\n")
        for i, line in enumerate(lines, 1):
            for m in DURATION.finditer(line):
                a, b = max(0, m.start() - 140), min(len(line), m.end() + 140)
                window = line[a:b]
                phrase = f"{m.group(1).lower()} {m.group(2).lower()}"
                for nm in NAME.finditer(window):
                    root = stem(nm.group(1))
                    if root in names:
                        key = root
                        hits[key][phrase].append(f"{Path(fname).stem}:{i}")
    return {k: v for k, v in hits.items() if len(v) > 1}


# ─────────────────────────────────────────────────────────────────────
# NGRAM
# ─────────────────────────────────────────────────────────────────────
def check_ngram(files: dict[str, str], n: int = 6, limit: int = 2) -> list[str]:
    grams: dict[tuple, list[str]] = defaultdict(list)
    for fname, text in files.items():
        for i, line in enumerate(text.split("\n"), 1):
            if is_speech(line):
                continue
            toks = re.findall(WORD, line.lower())
            for j in range(len(toks) - n + 1):
                grams[tuple(toks[j: j + n])].append(f"{Path(fname).stem}:{i}")
    out = []
    for g, where in grams.items():
        if len(where) >= limit:
            out.append(f"«{' '.join(g)}» — {len(where)}×: {', '.join(where[:4])}")
    return sorted(out, key=lambda s: -int(s.split("— ")[1].split("×")[0]))


# ─────────────────────────────────────────────────────────────────────
# GLUED
# ─────────────────────────────────────────────────────────────────────
GLUED = [
    ("наощупь", "на ощупь"), ("вобщем", "в общем"), ("вцелом", "в целом"),
    ("подмышкой", "под мышкой"), ("напротяжении", "на протяжении"),
    ("вполоборота", "вполоборота"), ("настолько-же", "настолько же"),
    ("вследующий", "в следующий"), ("втечение", "в течение"),
    ("несмотря на то", "несмотря на то"), ("зато же", "за то же"),
    ("вполголоса", "вполголоса"), ("наперевес", "наперевес"),
    ("посередине", "посередине"), ("вобрез", "в обрез"),
    ("вдоль", "вдоль"), ("наизготовку", "наизготовку"),
]
GLUED_BAD = {g: r for g, r in GLUED if g != r}


def check_glued(files: dict[str, str]) -> list[str]:
    out = []
    for fname, text in files.items():
        for i, line in enumerate(text.split("\n"), 1):
            low = line.lower()
            for bad, good in GLUED_BAD.items():
                if bad in low:
                    out.append(f"{Path(fname).stem}:{i} «{bad}» → «{good}»")
    return out


# ─────────────────────────────────────────────────────────────────────
# REFLECTION
# ─────────────────────────────────────────────────────────────────────
REFLECT_OPEN = re.compile(
    r"^Я\s+(понял\w*|поняла|сообразила|сообразил\w*|осознала|догадалась|"
    r"начала\s+понимать|поймала\s+себя|только\s+тогда|встала\s+прежде)",
)


def check_reflection(paras: list[tuple[int, str]]) -> list[tuple[int, str]]:
    return [(ln, p[:110]) for ln, p in paras if REFLECT_OPEN.match(p)]


# ─────────────────────────────────────────────────────────────────────
# TIMELINE
# ─────────────────────────────────────────────────────────────────────
CLOCK = re.compile(
    r"\b(в\s+(?:перв|втор|трет|четвёрт|пят|шест|седьм|восьм|девят|десят|"
    r"одиннадцат|двенадцат)\w*\s+часу|"
    r"в\s+половине\s+\w+|к\s+(?:двум|трём|четырём|пяти|шести|семи|восьми)|"
    r"ближе\s+к\s+полуночи|за\s?полночь|заполночь|"
    r"(?:перв|втор|трет|четвёрт|пят|шест|седьм|восьм)\w*\s+колокол\w*|"
    r"на\s+рассвете|к\s+рассвету|под\s+утро|"
    r"в\s+\w+\s+часу\s+ночи)\b",
    re.IGNORECASE,
)


def check_timeline(files: dict[str, str]) -> list[str]:
    out = []
    for fname, text in files.items():
        for i, line in enumerate(text.split("\n"), 1):
            for m in CLOCK.finditer(line):
                out.append(f"{Path(fname).stem}:{i}  {m.group(0)}")
    return out


# ─────────────────────────────────────────────────────────────────────
# служебное
# ─────────────────────────────────────────────────────────────────────
def is_speech(p: str) -> bool:
    return p.lstrip().startswith(("—", "–", "-"))


def quote(p: str, a: int, b: int, pad: int = 45) -> str:
    s = p[max(0, a - pad): min(len(p), b + pad)].replace("\n", " ")
    return ("…" if a - pad > 0 else "") + s + ("…" if b + pad < len(p) else "")


# ─────────────────────────────────────────────────────────────────────
# UNSOURCED — точное число в наррации, которое POV нечем измерить
# ─────────────────────────────────────────────────────────────────────
# См. SKILL-writing-craft.md §3.3. Число в тексте от первого лица
# законно, если героиня его сосчитала, отмерила телом, ей его назвали
# или она знает его по профессии. Всё прочее — число из воздуха.
#
# Самый частый подкласс — минуты: в Минте время бьют колоколами,
# часов у Сильвии нет, значит «через двадцать две минуты» она знать
# не может.

NUM_WORD = (
    r"(?:одну|две|двух|три|трёх|четыре|четырёх|пять|пяти|шесть|шести|"
    r"семь|семи|восемь|восьми|девять|девяти|десять|десяти|"
    r"одиннадцать|двенадцать|четырнадцать|пятнадцать|двадцать|"
    r"тридцать|сорок|пятьдесят|шестьдесят|\d+)"
)
TIME_UNIT = r"(?:минут\w*|секунд\w*|часа|часов)"

# «через двадцать две минуты», «за четыре минуты», «на шесть минут»
EXACT_TIME = re.compile(
    rf"(?:через|за|на|ещё)?\s*\b{NUM_WORD}\s+{TIME_UNIT}\b", re.IGNORECASE
)
# инверсия «минут пять», «секунд десять» — это оценка на глаз, законна
INVERTED = re.compile(rf"\b{TIME_UNIT}\s+{NUM_WORD}\b", re.IGNORECASE)
# вилка «две-три секунды», «пять-шесть минут» — тоже оценка
FORK = re.compile(rf"\b{NUM_WORD}\s*[-–—]\s*{NUM_WORD}\s+{TIME_UNIT}\b", re.IGNORECASE)

# признаки законного источника числа в той же фразе
SOURCED = re.compile(
    r"(?:счита\w*|посчита\w*|насчита\w*|досчита\w*|пересчита\w*|"
    r"мерил\w*|намерил\w*|отмерил\w*|"
    r"около|примерно|приблизительно|где-то|навскидку|наверное|"
    r"кажется|вроде|почти|с\s+лишним|с\s+небольшим|может|или)",
    re.IGNORECASE,
)


def check_unsourced(paras: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Точные единицы времени в наррации без источника у POV."""
    out = []
    for ln, p in paras:
        if p.startswith(("—", "«", "*", "#")):      # реплики и служебное
            continue
        for m in EXACT_TIME.finditer(p):
            frag = m.group(0).strip()
            if INVERTED.search(frag):
                continue
            lo0 = max(0, m.start() - 12)
            if FORK.search(p[lo0:m.end()]):
                continue
            # окно вокруг числа: есть ли рядом счёт или хедж
            lo, hi = max(0, m.start() - 90), min(len(p), m.end() + 60)
            if SOURCED.search(p[lo:hi]):
                continue
            out.append((ln, f"«{frag}» — чем измерено? … {p[lo:hi].strip()[:110]}"))
    return out


def paragraphs(text: str) -> list[tuple[int, str]]:
    out = []
    for i, line in enumerate(text.split("\n"), 1):
        if line.strip() and line.strip() != "---":
            out.append((i, line.strip()))
    return out


def load_names(files: dict[str, str] | None = None) -> set[str]:
    """Имена собственные: из реестра фактов плюс частые в самом тексте.

    Реестра мало: Хельга в нём есть не всегда, а сроки её работы
    разъезжаются между главами именно потому, что имя не в списке.
    """
    names: set[str] = set()
    p = Path("01-canon/FACTS.tsv")
    if p.exists():
        for line in p.read_text(encoding="utf-8").split("\n"):
            if line.startswith("#") or "\t" not in line:
                continue
            val = line.split("\t")[1].strip()
            for w in re.findall(r"[А-ЯЁ][а-яё]{3,}", val):
                names.add(stem(w))
    if files:
        freq: dict[str, int] = defaultdict(int)
        for text in files.values():
            for line in text.split("\n"):
                for m in CAP_WORD.finditer(line):
                    freq[stem(m.group(1))] += 1
        names |= {s for s, n in freq.items() if n >= 3}
    return names


# ─────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--all", action="store_true", help="все главы рукописи")
    ap.add_argument("--object", metavar="СЛОВО",
                    help="показать все упоминания предмета: сверка второго называния")
    ap.add_argument("--ngram", type=int, default=6)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    paths = args.files
    if args.all:
        paths = sorted(glob.glob("03-manuscript/arc-*/ch-*.md"))
    if not paths:
        ap.error("не заданы файлы (или --all)")

    files = {p: Path(p).read_text(encoding="utf-8") for p in paths}

    # --object: не проверка, а выписка для глаза
    if args.object:
        pat = re.compile(args.object, re.IGNORECASE)
        for fname, text in files.items():
            for i, line in enumerate(text.split("\n"), 1):
                if pat.search(line):
                    print(f"{Path(fname).stem}:{i}  {line.strip()[:200]}")
        return 0

    total = 0

    def head(title: str, n: int) -> None:
        print(f"\n=== {title}: {n}")

    # пофайловые
    for fname, text in files.items():
        paras = paragraphs(text)
        stem_name = Path(fname).stem
        for title, res in (
            ("POV_GENDER", check_pov_gender(paras)),
            ("INDIRECT", check_indirect(paras)),
        ):
            if res:
                total += len(res)
                print(f"\n=== {title} [{stem_name}]: {len(res)}")
                for ln, q in res:
                    print(f"  {ln}: {q}")

    nv = check_name_variants(files)
    if nv:
        total += len(nv)
        head("NAME_VARIANTS", len(nv))
        for s in nv:
            print(f"  {s}")

    gl = check_glued(files)
    if gl:
        total += len(gl)
        head("GLUED", len(gl))
        for s in gl:
            print(f"  {s}")

    dur = check_duration(files, load_names(files))
    if dur:
        head("DURATION", len(dur))
        for name, variants in sorted(dur.items()):
            print(f"  {name}*:")
            for phrase, where in sorted(variants.items(), key=lambda kv: -len(kv[1])):
                print(f"      {phrase:<20} {', '.join(where[:5])}")

    ng = check_ngram(files, args.ngram)
    if ng:
        head(f"NGRAM ({args.ngram} слов, повтор в наррации)", len(ng))
        for s in ng[:25]:
            print(f"  {s}")

    if not args.quiet:
        for fname, text in files.items():
            uns = check_unsourced(paragraphs(text))
            if uns:
                print(f"\n=== UNSOURCED [{Path(fname).stem}]: {len(uns)}  "
                      f"(точное время без источника у POV, §3.3)")
                for ln, q in uns:
                    print(f"  {ln}: {q}")

        for fname, text in files.items():
            refl = check_reflection(paragraphs(text))
            if refl:
                print(f"\n=== REFLECTION [{Path(fname).stem}]: {len(refl)}  "
                      f"(проверить: не должно ли стоять выше)")
                for ln, q in refl:
                    print(f"  {ln}: {q}")

        tl = check_timeline(files)
        if tl:
            print(f"\n=== TIMELINE: {len(tl)}  (читать подряд, часы должны расти)")
            for s in tl:
                print(f"  {s}")

    print(f"\nжёстких срабатываний: {total}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
