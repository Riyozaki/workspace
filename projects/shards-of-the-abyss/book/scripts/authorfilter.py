#!/usr/bin/env python3
"""Фильтр по прямому списку автора (август 2026).

Отличие от `style_guard.py`: тот калиброван на старые нормы и ловит
`не X, а Y` буквально. Автор сформулировал шире:

  «конструкции не, а или начать предложение с не и тройные кластеры»
  «"убийство это не жестокость, это возможность стать сильнее" — это полная шляпа»

То есть дефект — не запятая с «а», а **определительная риторика**: персонаж
или наррация объясняет читателю смысл через формулу «X это Y», вместо того
чтобы говорить как живой человек в своей сцене.

Категории:
  DEF_ETO      — определение через «это»: «X — это Y», «убийство это Y»
  NEG_DEF      — отрицательное определение: «это не X, это Y», «не X. Y.»
  NEG_START    — предложение начинается с «Не ...»
  TRIPLE       — тройные кластеры (перечисления по три)
  SENT_CLOSER  — сентенция в финале сцены/главы (последний абзац блока)
  FILTER       — фильтрные слова: «я поняла, что», «я почувствовала, что»
  TEXTBOOK     — «дело в том, что», «в том-то и дело», «вот что значит»

Запуск:
    python3 scripts/authorfilter.py 03-manuscript/arc-01/ch-01.md
    python3 scripts/authorfilter.py --code NEG_START 03-manuscript/arc-*/ch-*.md
    python3 scripts/authorfilter.py --quiet 03-manuscript/arc-*/ch-*.md
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

# --------------------------------------------------------------------------
# Разбор текста
# --------------------------------------------------------------------------

ABBREV = {"т", "г", "гл", "им", "др", "пр", "см", "стр", "св"}


def split_sentences(block: str):
    """Грубое деление на предложения с сохранением позиции."""
    out = []
    start = 0
    i = 0
    n = len(block)
    while i < n:
        ch = block[i]
        if ch in ".!?…":
            j = i + 1
            while j < n and block[j] in ".!?…»\"'":
                j += 1
            if j < n and block[j] not in " \n":
                i = j
                continue
            frag = block[start:j].strip()
            if frag:
                word = re.findall(r"[А-Яа-яЁёA-Za-z]+", frag[-6:])
                if not (word and word[-1].lower() in ABBREV):
                    out.append((start, frag))
                    start = j
            i = j
            continue
        i += 1
    tail = block[start:].strip()
    if tail:
        out.append((start, tail))
    return out


def is_dialogue(line: str) -> bool:
    s = line.strip()
    return s.startswith("—") or (s.startswith("*") and not s.startswith("**")) or (
        s.startswith("«") and s.rstrip().endswith(("»", "».", "»?", "»!"))
    )


def paragraphs(text: str):
    """Возвращает (номер строки, текст абзаца, это_диалог)."""
    out = []
    line_no = 1
    for raw in text.split("\n"):
        s = raw.strip()
        if s and not s.startswith(("#", ">", "|", "---", "```")):
            out.append((line_no, s, is_dialogue(raw)))
        line_no += 1
    return out


# --------------------------------------------------------------------------
# Правила
# --------------------------------------------------------------------------

# «X — это Y» как формула определения.
#
# Высокая точность важнее полноты: «Ты это вчера говорила» и «Он сказал это
# без похвалы» — не определения, там «это» стоит дополнением. Дефект автора —
# именно связка «понятие — это понятие», где текст объясняет читателю смысл.
#
# Ловим два надёжных случая:
#   1. тире + «это» + существительное  («убийство — это возможность»)
#   2. «X это Y» без тире, когда слева существительное в им. падеже, а справа
#      тоже существительное («убийство это необходимость»)
RE_DEF_ETO = re.compile(
    r"(?:^|[.!?;]\s|—\s)"
    r"(?P<subj>(?!Меня\b|Тебя\b|Его\b|Её\b|Нас\b|Вас\b|Их\b|Мне\b|Тебе\b|Ему\b|Нам\b|Вам\b|"
    r"Тогда\b|Потом\b|Значит\b|Просто\b|Может\b|Вроде\b|Разве\b|Опять\b|Снова\b|Всё\b|Всего\b|"
    r"Пусть\b|Даже\b|Если\b|Когда\b|Пока\b|Раз\b|Вот\b|Зато\b|Хотя\b)"
    r"[А-ЯЁа-яё][а-яё]{3,})\s+"
    r"(?:—\s+)?это\s+"
    r"(?P<pred>(?!бы\b|же\b|уже\b|всё\b|все\b|я\b|ты\b|он\b|она\b|они\b|мы\b|вы\b|"
    r"тот\b|та\b|то\b|те\b|тут\b|там\b|здесь\b|сейчас\b|тогда\b|потом\b|значит\b|"
    r"правда\b|конечно\b|точно\b|хорошо\b|плохо\b|много\b|мало\b|надо\b|можно\b|"
    r"нельзя\b|не\b|его\b|её\b|их\b|мой\b|моя\b|моё\b|твой\b|наш\b|ваш\b|такой\b|"
    r"такая\b|такое\b|важно\b|странно\b|нормально\b|понятно\b|видно\b|слышно\b)"
    r"[а-яё]{4,})",
    re.IGNORECASE,
)

# Явно учебниковые определительные шаблоны — ловятся всегда.
RE_DEF_TEMPLATE = re.compile(
    r"\b(?:есть не что иное|заключается в том, что|"
    r"[а-яё]{4,}\s+—\s+(?:это\s+)?когда\b)",
    re.IGNORECASE,
)

# Отрицательное определение: «это не X, это Y» / «не X. Это Y.»
RE_NEG_DEF = [
    ("NEG_DEF_ETO_ETO", re.compile(r"\bэто\s+не\s+[^.!?\n]{2,60}[,.]\s*(?:а\s+)?это\b", re.IGNORECASE)),
    ("NEG_DEF_DASH", re.compile(r"\bне\s+[а-яё]{3,}[^.!?\n]{0,40}\s+—\s+(?!сказал|сказала|спросил|спросила|"
                                r"ответил|ответила|проговорил|проговорила|бросил|бросила|отозвал|отозвалась|"
                                r"добавил|добавила|повторил|повторила|начал|начала|продолжил|продолжила|"
                                r"перебил|перебила|заметил|заметила|уточнил|уточнила|позвал|позвала|"
                                r"крикнул|крикнула|пробормотал|пробормотала|согласился|согласилась|"
                                r"кивнул|кивнула|усмехнул|усмехнулась|подтвердил|подтвердила)[а-яё]",
                                re.IGNORECASE)),
    ("NEG_DEF_A", re.compile(r"\bне\s+[^.!?\n;]{2,70},\s*а\s+(?!я\b|ты\b|он\b|она\b|мы\b|вы\b|они\b|то\b|"
                             r"потом|затем|дальше|значит|может|вдруг|уже|ещё|еще|тут|там|теперь)[а-яё]",
                             re.IGNORECASE)),
    ("NEG_DEF_PROSTO", re.compile(r"\bне\s+[^.!?\n;]{2,70},\s*(?:просто|только|скорее|зато)\b", re.IGNORECASE)),
]

# Предложение начинается с «Не ...».
#
# Живой запрет в реплике («Не надо», «Не открывай на улице») — нормальная речь,
# её трогать нельзя. Дефект — наррация, которая открывает предложение отрицанием
# вместо прямого утверждения: «Не то чтобы...», «Не потому, что...», «Не от
# звука и не от света».
RE_NEG_START = re.compile(r"^Не\s+[а-яё]", re.UNICODE)

# Императив/разговорный отклик — не считать дефектом.
NEG_START_OK = re.compile(
    r"^Не\s+(?:надо|нужно|стоит|смей|смейте|трогай|трогайте|открывай|открывайте|"
    r"ходи|ходите|говори|говорите|бойся|бойтесь|лезь|лезьте|спеши|спешите|"
    r"двигайся|двигайтесь|шевелись|молчи|молчите|плачь|плачьте|мешай|мешайте|"
    r"спрашивай|спрашивайте|беспокойся|волнуйся|переживай|дури|начинай|"
    r"вздумай|вздумайте|за\s+что|знаю|помню|уверен|уверена|хочу|буду|стану|могу|"
    r"понимаю|слышу|вижу|скажу|дам|дождёшься|дождетесь|сейчас|сегодня|сразу|очень|"
    r"так\s+уж|особо|особенно|совсем|только|всегда|обязательно)\b",
    re.IGNORECASE,
)

# Фильтрные слова.
RE_FILTER = re.compile(
    r"\b(?:я\s+)?(?:понял[аи]?|почувствовал[аи]?|осознал[аи]?|заметил[аи]?|увидел[аи]?|"
    r"подумал[аи]?|решил[аи]?|вспомнил[аи]?)[,]?\s+что\b",
    re.IGNORECASE,
)

# Учебниковые связки.
RE_TEXTBOOK = re.compile(
    r"\b(?:дело в том,?\s+что|в том-то и дело|вот что значит|именно поэтому|"
    r"по сути\b|как известно|в сущности|таким образом|иными словами|"
    r"суть в том|смысл в том|правда в том|разница в том)\b",
    re.IGNORECASE,
)

# Сентенция: обобщающий субъект + гномический презенс, без дейксиса.
#
# Ключ — «человек» как класс, а не как персонаж сцены. «Человек в фартуке
# записывал» — это конкретный человек в прошедшем времени, не сентенция.
# Поэтому требуем: обобщающее подлежащее И настоящее время И отсутствие
# конкретизирующего определения справа.
GENERIC_SUBJ = re.compile(
    r"(?:^|[.!?;,]\s|—\s)(?:люди|человек|все|всякий|каждый|никто|любой|большинство|"
    r"тот,?\s+кто|те,?\s+кто|кто\s+угодно)\b"
    r"(?!\s+(?:в\s|за\s|с\s|у\s|на\s|из\s|под\s|перед\s|около\s|по\s|при\s)"
    r"|\s+[а-яё]+(?:ом|ой|ым|е)\b)",
    re.IGNORECASE,
)

# Гномический презенс: вневременное настоящее.
GNOMIC = re.compile(
    r"\b[а-яё]{3,}(?:ет|ёт|ут|ют|ит|ат|ят|ется|ются|ится|атся|ятся|ают|еют)\b",
    re.IGNORECASE,
)

# Прошедшее время = рассказ о конкретном событии, не сентенция.
PAST_TENSE = re.compile(
    r"\b[а-яё]{3,}(?:ал|ала|али|ало|ил|ила|или|ило|ел|ела|ели|ело|ул|ула|ули|уло|"
    r"ыл|ыла|ыли|ыло|шёл|шла|шли|лся|лась|лись|лось)\b",
    re.IGNORECASE,
)
DEIXIS = re.compile(r"\b(?:я|мне|меня|мной|ты|тебе|тебя|тобой|мы|нам|нас|вы|вам|вас|"
                    r"здесь|сейчас|сегодня|вчера|завтра|тут|этот|эта|эти|этого|этой)\b",
                    re.IGNORECASE)

# Клише.
CLICHE = [
    (r"глубок\w+ вздох", "глубокий вздох"),
    (r"сердце (?:сжал|ёкнул|екнул|заколотил|пропустил)\w*", "сердце-клише"),
    (r"уголк\w* губ", "уголки губ"),
    (r"краешк\w* губ", "краешки губ"),
    (r"костяшк\w*", "костяшки"),
    (r"повисл\w+ (?:тишина|молчание|пауза)", "повисла тишина"),
    (r"по спине пробежал", "мороз по спине"),
    (r"холод\w* (?:пробежал|прокатил)\w*", "холод пробежал"),
    (r"\bкомок в горле\b", "комок в горле"),
    (r"\bнечто\b", "нечто"),
    (r"что-то внутри", "что-то внутри"),
    (r"в этот момент", "в этот момент"),
    (r"каким-то образом", "каким-то образом"),
    (r"по-настоящему", "по-настоящему"),
    (r"словно бы", "словно бы"),
    (r"кровь застыла", "кровь застыла"),
    (r"внутри всё (?:оборвал|сжал|похолодел)\w*", "внутри всё оборвалось"),
]
CLICHE = [(re.compile(p, re.IGNORECASE), name) for p, name in CLICHE]


def find_triples(sent: str):
    """Тройные кластеры: ровно три однородных члена, замкнутые границей.

    Ловим только замкнутый ряд: после третьего элемента идёт конец
    предложения, тире или двоеточие. Открытый ряд «A, B, C, D» — это
    перечисление, а не ритмическая тройка, и автор их не запрещал.
    """
    hits = []
    pattern = re.compile(
        r"(?<![,\w])\s*"
        r"([А-ЯЁа-яё][а-яё]{3,}),\s+"
        r"([а-яё]{3,}),\s+"
        r"(?:и\s+)?([а-яё]{3,})"
        r"(?=\s*(?:[.!?;:—…]|$))",
    )
    for m in pattern.finditer(sent):
        a, b, c = m.group(1).lower(), m.group(2), m.group(3)
        tails = {a[-2:], b[-2:], c[-2:]}
        # одинаковая морфология хвоста = ритмическая тройка
        if len(tails) <= 2:
            hits.append(m.group(0).strip())
    # «A, B и C» внутри предложения — тоже тройка, если все три однословные
    for m in re.finditer(
        r"(?<![,\w])([А-ЯЁа-яё][а-яё]{4,}),\s+([а-яё]{4,})\s+и\s+([а-яё]{4,})(?![\w-])",
        sent,
    ):
        a, b, c = m.group(1).lower(), m.group(2), m.group(3)
        # первый элемент должен делить морфологию хотя бы с одним из двух:
        # иначе это не тройка, а пара при постороннем существительном
        # («в планшете, разбирал и собирал»).
        if a[-2:] in {b[-2:], c[-2:]}:
            hits.append(m.group(0).strip())
    return hits


# --------------------------------------------------------------------------
# Анализ файла
# --------------------------------------------------------------------------


def analyse(path: Path, only=None):
    text = path.read_text(encoding="utf-8")
    findings = []
    paras = paragraphs(text)

    # Границы сцен: строки «---» делят главу на блоки.
    scene_breaks = set()
    for i, raw in enumerate(text.split("\n"), start=1):
        if raw.strip() == "---":
            scene_breaks.add(i)

    seen = set()

    def add(code, line, excerpt, note):
        if only and code not in only:
            return
        key = (code, line, excerpt.strip()[:60])
        if key in seen:
            return
        seen.add(key)
        findings.append((code, line, excerpt.strip(), note))

    last_para_of_scene = set()
    prev = None
    for ln, body, dial in paras:
        if prev is not None and any(prev[0] < b < ln for b in scene_breaks):
            last_para_of_scene.add(prev[0])
        prev = (ln, body)
    if prev:
        last_para_of_scene.add(prev[0])

    for ln, body, dial in paras:
        sents = split_sentences(body)

        for _, s in sents:
            core = s.lstrip("—*«»\"' ").strip()

            # DEF_ETO
            for m in RE_DEF_ETO.finditer(s):
                seg = s[max(0, m.start() - 20): m.end() + 45]
                add("DEF_ETO", ln, seg, "определение «X — это Y» — формула вместо живой речи")
            for m in RE_DEF_TEMPLATE.finditer(s):
                add("DEF_ETO", ln, s[max(0, m.start() - 20): m.end() + 45],
                    "учебниковое определение")

            # NEG_DEF
            for code, rx in RE_NEG_DEF:
                for m in rx.finditer(s):
                    add(code, ln, m.group(0), "отрицательное определение")

            # NEG_START — только в наррации и только не-императив
            if RE_NEG_START.match(core) and not NEG_START_OK.match(core):
                if not dial:
                    add("NEG_START", ln, core[:110],
                        "наррация открывает предложение отрицанием")

            # FILTER
            for m in RE_FILTER.finditer(s):
                add("FILTER", ln, s[max(0, m.start() - 30): m.end() + 30],
                    "фильтрное слово — прямой доступ вместо посредника")

            # TEXTBOOK
            for m in RE_TEXTBOOK.finditer(s):
                add("TEXTBOOK", ln, s[max(0, m.start() - 30): m.end() + 40],
                    "учебниковая связка")

            # TRIPLE
            for t in find_triples(s):
                add("TRIPLE", ln, t, "тройной кластер")

            # CLICHE
            for rx, name in CLICHE:
                if rx.search(s):
                    add("CLICHE", ln, s[:110], f"клише: {name}")

            # SENTENTIOUS: обобщающий субъект + настоящее время + нет дейксиса
            # + нет прошедшего (иначе это рассказ о событии, а не суждение).
            words = re.findall(r"[А-Яа-яЁё-]+", core)
            if (
                4 <= len(words) <= 26
                and GENERIC_SUBJ.search(core)
                and GNOMIC.search(core)
                and not DEIXIS.search(core)
                and not PAST_TENSE.search(core)
                and not re.search(r"\d", core)
            ):
                add("SENTENTIOUS", ln, core[:130],
                    "обобщение о людях в настоящем времени без дейксиса")

        # SENT_CLOSER: последний абзац сцены с обобщением или формулой
        if ln in last_para_of_scene:
            tail = sents[-1][1] if sents else body
            core = tail.lstrip("—*«»\"' ").strip()
            words = re.findall(r"[А-Яа-яЁё-]+", core)
            if len(words) <= 22:
                if GENERIC_SUBJ.search(core) or RE_DEF_ETO.search(" " + core):
                    add("SENT_CLOSER", ln, core[:130],
                        "финал сцены закрыт формулой/обобщением")

    return findings, text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Фильтр по списку автора")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--code", action="append", default=None,
                    help="показать только эти коды (можно несколько раз)")
    ap.add_argument("--quiet", action="store_true", help="только сводка")
    ap.add_argument("--limit", type=int, default=0, help="максимум находок на файл")
    args = ap.parse_args(argv)

    only = set(args.code) if args.code else None
    grand = Counter()
    per_file = {}

    for p in [Path(x) for x in args.paths]:
        if not p.exists():
            print(f"нет файла: {p}", file=sys.stderr)
            return 2
        findings, _ = analyse(p, only)
        per_file[p] = findings
        for code, *_ in findings:
            grand[code] += 1

        if not args.quiet and findings:
            print(f"\n=== {p} ===")
            shown = findings if not args.limit else findings[: args.limit]
            for code, line, excerpt, note in shown:
                print(f"[{code}] стр.{line}: {excerpt}")
                print(f"    → {note}")
            if args.limit and len(findings) > args.limit:
                print(f"    ... ещё {len(findings) - args.limit}")

    print("\n--- сводка ---")
    width = max((len(c) for c in grand), default=10)
    for code, n in grand.most_common():
        print(f"{code:<{width}}  {n}")
    print(f"{'ВСЕГО':<{width}}  {sum(grand.values())}")

    if len(per_file) > 1:
        print("\n--- по файлам ---")
        for p, f in per_file.items():
            if f:
                print(f"{p.name:<12} {len(f)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
