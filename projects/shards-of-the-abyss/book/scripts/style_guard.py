#!/usr/bin/env python3
"""Жёсткий guard художественной прозы проекта shardsoftheabyss.

Версия 2.

Главное отличие от версии 1: guard проверяет не только словарь, но и **ритм**.
Практика показала, что лексические баны текст проходит легко, а разваливается
он на другом — на рубленом синтаксисе, анафорах и самоповторе. Именно эти
дефекты автор ловит глазами, а guard v1 их не видел вообще.

Категории проверок:
  1. LEX     — запрещённая лексика и конструкции (было в v1)
  2. RHYTHM  — рубленый синтаксис, анафоры, назывные цепочки (новое)
  3. REPEAT  — самоповтор внутри файла и между файлами (новое)
  4. FORM    — одиночные слова-абзацы, плотность образности

Опорная норма ритма взята из `03-manuscript/arc-01-v4-combined.md` —
текста, который автор признал живым.
"""

from __future__ import annotations

import argparse
import bisect
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


# ---------------------------------------------------------------------------
# Модель находки
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    severity: str  # BLOCKER | WARN
    code: str
    line: int
    excerpt: str
    message: str


SEVERITY_ORDER = {"BLOCKER": 0, "WARN": 1}


# ---------------------------------------------------------------------------
# 1. LEX — лексические блокеры
# ---------------------------------------------------------------------------

BLOCKER_PATTERNS = [
    ("NEG_CONTRAST_A", re.compile(r"\bне\b[^\n.!?;]{0,80},\s*а\b", re.IGNORECASE),
     "отрицательная контрастная конструкция `не ..., а ...`"),
    ("NEG_CONTRAST_PROSTO", re.compile(r"\bне\b[^\n.!?;]{0,80},\s*просто\b", re.IGNORECASE),
     "отрицательная конструкция `не ..., просто ...`"),
    ("NEG_CONTRAST_TOLKO", re.compile(r"\bне\b[^\n.!?;]{0,80},\s*только\b", re.IGNORECASE),
     "отрицательная конструкция `не ..., только ...`"),
    ("NEG_CONTRAST_ZATO", re.compile(r"\bне\b[^\n.!?;]{0,80},\s*зато\b", re.IGNORECASE),
     "отрицательная конструкция `не ..., зато ...`"),
    ("NEG_CONTRAST_SKOREE", re.compile(r"\bне\b[^\n.!?;]{0,80},?\s*скорее\b", re.IGNORECASE),
     "отрицательная конструкция `не ..., скорее ...`"),
    # Тире-контраст `Не резало — тянуло`. Запятая перед тире означает слова автора
    # в диалоге («— Ты не ела, — сказала она»), поэтому такие случаи исключены.
    ("NEG_CONTRAST_DASH", re.compile(
        r"\bне\b[^\n.!?;,—]{0,50}\s+—\s+(?!сказал|спросил|ответил|проговорил|бросил|отозвал|"
        r"добавил|повторил|начал|продолжил|перебил|заметил|уточнил|позвал|крикнул|пробормотал)[а-яё]",
        re.IGNORECASE),
     "отрицательная контрастная конструкция через тире `не X — Y`"),
    ("NEG_SPLIT_ETO", re.compile(r"Это\s+(?:была\s+|был\s+|было\s+)?не\b[^\n.!?]{0,70}[.!?]\s+Это\s", re.IGNORECASE),
     "дробная отрицательная конструкция `Это не X. Это Y.`"),
    ("NEG_SPLIT_DOUBLE", re.compile(r"(?:^|[.!?»]\s)\s*Не\b[^\n.!?]{0,40}[.!?]\s+Не\b[^\n.!?]{0,40}[.!?]"),
     "дробный отрицательный кластер `Не X. Не Y.`"),
    ("BANNED_KOSTYASHKI", re.compile(r"костяш", re.IGNORECASE), "запрещённый маркер `костяшки`"),
    ("BANNED_UGOLKI_GUB", re.compile(r"уголк\w* губ", re.IGNORECASE), "запрещённый маркер `уголки губ`"),
    ("BANNED_KRAESHKI_GUB", re.compile(r"краешк\w* губ", re.IGNORECASE), "запрещённый маркер `краешки губ`"),
    ("BANNED_GLUBOKIY_VZDOH", re.compile(r"глубок\w* вздох", re.IGNORECASE), "запрещённый маркер `глубокий вздох`"),
    ("BANNED_POVISLA_TISHINA", re.compile(r"повисл\w* тишин", re.IGNORECASE), "запрещённый маркер `повисла тишина`"),
    ("BANNED_NECHTO", re.compile(r"\bнечто\b", re.IGNORECASE), "запрещённый маркер `нечто`"),
    ("BANNED_CHTO_TO_VNUTRI", re.compile(r"что-то внутри", re.IGNORECASE), "запрещённый маркер `что-то внутри`"),
    ("BANNED_V_ETOT_MOMENT", re.compile(r"в этот момент", re.IGNORECASE), "запрещённый маркер `в этот момент`"),
    ("BANNED_KAKIM_TO_OBRAZOM", re.compile(r"каким-то образом", re.IGNORECASE), "запрещённый маркер `каким-то образом`"),
    ("BANNED_PO_NASTOYASHCHEMU", re.compile(r"по-настоящему", re.IGNORECASE), "запрещённый маркер `по-настоящему`"),
    ("BANNED_OSOZNAL_CHTO", re.compile(r"осознал\w*,? что", re.IGNORECASE), "запрещённый маркер `осознал, что`"),
    ("BANNED_POCHUVSTVOVAL_CHTO", re.compile(r"почувствовал\w*,? что", re.IGNORECASE), "запрещённый маркер `почувствовал, что`"),
    ("BANNED_SERDTSE_SJALOS", re.compile(r"сердце сжал\w*", re.IGNORECASE), "запрещённый маркер `сердце сжалось`"),
    ("BANNED_SERDTSE_YOK", re.compile(r"сердце [её]кнул\w*", re.IGNORECASE), "запрещённый маркер `сердце ёкнуло`"),
    ("BANNED_SLOVNO_BY", re.compile(r"словно бы", re.IGNORECASE), "подозрительный маркер `словно бы`"),
]

# Псевдотелесная абстракция: состояние подаётся как самостоятельный субъект.
PSEUDO_BODY = re.compile(
    r"\b(?:пришл[аио]|вернул(?:ся|ась|ось)|вошл[аио]|ушл[аио]|поднял(?:ся|ась)|"
    r"накрыл[аио]?|отпустил[аио]?)\s+(?:голова|боль|воздух|тело|темнота|страх|тошнота|слабость)\b",
    re.IGNORECASE,
)

# Метатекстовые метафоры — герой не знает, что он в книге.
METATEXT = re.compile(r"\b(?:черновик\w*|сюжет\w*|эт[ао]й? истори[ие]|глав[аеы] жизни|сценари\w+)\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# 2. RHYTHM — ритмические блокеры
# ---------------------------------------------------------------------------

# Норма, снятая сплошным замером 31 главы (август 2026, CALIBRATION.md §1).
# Эталон — арки 1-2 и глава 10:
#   средняя длина предложения наррации 10-12 слов
#   доля предложений <= 4 слов 20-25%
#   доля предложений >= 12 слов 35-45%
#
# ВАЖНО: прежние пороги были сняты с архивного черновика (норма 7,5) и
# оказались нижней границей брака. Арка 5 книги (7,9 / 41% коротких)
# в старые пороги проходила, и это скрывало прогрессирующее дробление.
STACCATO_WINDOW = 40          # предложений в скользящем окне
STACCATO_WARN_RATIO = 0.30    # выше — предупреждение
STACCATO_BLOCK_RATIO = 0.38   # выше — блокер

# Безглагольные предложения. Норма арок 1-2 — 3-7%, в арке 5 доходило до 18%.
VERBLESS_WARN_RATIO = 0.10
VERBLESS_BLOCK_RATIO = 0.16

# Предложений на абзац наррации. Норма арки 1 — 2,1.
FRAGMENT_WARN_RATIO = 2.5
FRAGMENT_BLOCK_RATIO = 2.9

# Глаголы: для поиска назывных (безглагольных) цепочек.
VERB_ENDINGS = re.compile(
    r"\w+(?:ал|ала|али|ало|ил|ила|или|ило|ел|ела|ели|ело|ул|ула|ули|уло|"
    r"ыл|ыла|ыли|ыло|ёл|шла|шли|шло|ет|ёт|ут|ют|ит|ат|ят|ешь|ишь|ем|им|ете|ите|"
    r"ть|ться|тся|л[ao]сь|лись|ло|ла)\b",
    re.IGNORECASE,
)

# Вводные слова — их нельзя считать элементом ритмической тройки.
PARENTHETICALS = {
    "скорее", "всего", "судя", "похоже", "надеюсь", "кажется", "конечно", "например",
    "возможно", "наверное", "видимо", "правда", "впрочем", "значит", "пожалуй",
    "разумеется", "по-моему", "к счастью", "к сожалению", "может",
}

ANAPHORA_MIN_RUN = 3          # сколько одинаковых зачинов подряд считать нарушением
ANAPHORA_MAX_WORDS = 7        # только для коротких фраз

NOMINATIVE_MIN_RUN = 3        # сколько безглагольных предложений подряд
NOMINATIVE_MAX_WORDS = 5


# ---------------------------------------------------------------------------
# 3. REPEAT — самоповтор
# ---------------------------------------------------------------------------

DIALOGUE_TAG = re.compile(r"^—\s*(?:спросил|сказал|ответил|проговорил|бросил|отозвал)\w*\s+\w+\.?$", re.IGNORECASE)
TAG_LIMIT_PER_10K = 8         # сколько раз один и тот же тег допустим на 10k слов
SENTENCE_MIN_WORDS_FOR_DUPE = 4


# ---------------------------------------------------------------------------
# Вспомогательное
# ---------------------------------------------------------------------------


def build_line_index(text: str) -> List[int]:
    starts = [0]
    for idx, ch in enumerate(text):
        if ch == "\n":
            starts.append(idx + 1)
    return starts


def offset_to_line(offset: int, starts: List[int]) -> int:
    return bisect.bisect_right(starts, offset)


def excerpt_at(text: str, start: int, end: int) -> str:
    s = max(0, start - 40)
    e = min(len(text), end + 50)
    return text[s:e].replace("\n", " ").strip()


def is_prose_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    return not s.startswith(("#", ">", "```", "|", "- ", "* ", "1.", "2."))


def is_dialogue_line(line: str) -> bool:
    s = line.strip()
    # Обычная реплика.
    if s.startswith("—"):
        return True
    # Реплика внутреннего голоса: в проекте оформляется курсивом (*...*).
    # Без этой ветки речь Тени попадала в замер ритма наррации и искажала его.
    if s.startswith("*") and not s.startswith("**"):
        return True
    # Мысленный ответ Сильвии Тени: оформляется «ёлочками» отдельным абзацем.
    # Дефект найден на главе 20: 30 таких реплик считались наррацией и
    # завышали VERBLESS_DENSITY и долю коротких предложений.
    if s.startswith("«") and s.rstrip().endswith(("»", "».", "»?", "»!")):
        return True
    return False


def split_sentences(block: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?…])\s+", block) if s.strip()]


def word_count(s: str) -> int:
    return len(re.findall(r"[А-Яа-яЁёA-Za-z0-9-]+", s))


def first_word(s: str) -> str:
    m = re.search(r"[А-Яа-яЁёA-Za-z]+", s)
    return m.group(0).lower() if m else ""


def has_verb(s: str) -> bool:
    return bool(VERB_ENDINGS.search(s))


# ---------------------------------------------------------------------------
# Сканеры
# ---------------------------------------------------------------------------


def scan_lexical(text: str, starts: List[int]) -> Iterable[Finding]:
    for code, pattern, message in BLOCKER_PATTERNS:
        for m in pattern.finditer(text):
            yield Finding("BLOCKER", code, offset_to_line(m.start(), starts),
                          excerpt_at(text, m.start(), m.end()), message)
    for m in PSEUDO_BODY.finditer(text):
        yield Finding("BLOCKER", "PSEUDO_BODY", offset_to_line(m.start(), starts),
                      excerpt_at(text, m.start(), m.end()),
                      "псевдотелесная абстракция: состояние подано как самостоятельный субъект")
    for m in METATEXT.finditer(text):
        yield Finding("WARN", "METATEXT_METAPHOR", offset_to_line(m.start(), starts),
                      excerpt_at(text, m.start(), m.end()),
                      "возможная метатекстовая метафора; герой не знает, что он в книге")


def iter_narration_sentences(text: str):
    """Возвращает (offset, sentence) только для наррации, без реплик и заголовков."""
    offset = 0
    for line in text.splitlines(keepends=True):
        if is_prose_line(line) and not is_dialogue_line(line):
            base = offset
            for s in split_sentences(line):
                pos = line.find(s, base - offset)
                yield offset + (pos if pos >= 0 else 0), s
                base = offset + (pos if pos >= 0 else 0) + len(s)
        offset += len(line)


def scan_staccato(text: str, starts: List[int]) -> Iterable[Finding]:
    items = [(o, s) for o, s in iter_narration_sentences(text) if word_count(s) > 0]
    if len(items) < STACCATO_WINDOW:
        return
    flags = [1 if word_count(s) <= 4 else 0 for _, s in items]
    worst = None
    for i in range(0, len(items) - STACCATO_WINDOW + 1):
        ratio = sum(flags[i:i + STACCATO_WINDOW]) / STACCATO_WINDOW
        if worst is None or ratio > worst[0]:
            worst = (ratio, i)
    total_ratio = sum(flags) / len(flags)
    avg = sum(word_count(s) for _, s in items) / len(items)

    if total_ratio >= STACCATO_BLOCK_RATIO:
        sev, msg = "BLOCKER", "рубленый синтаксис по всему файлу"
    elif total_ratio >= STACCATO_WARN_RATIO:
        sev, msg = "WARN", "синтаксис заметно рубленее нормы проекта"
    else:
        sev = None
        msg = ""
    if sev:
        yield Finding(sev, "STACCATO_GLOBAL", 1,
                      f"средняя длина предложения наррации {avg:.1f} сл., коротких (<=4 сл.) {total_ratio:.0%}",
                      f"{msg}; ориентир арки 1 — ~7.6 сл. и ~20% коротких")

    if worst and worst[0] >= STACCATO_BLOCK_RATIO:
        o = items[worst[1]][0]
        yield Finding("BLOCKER", "STACCATO_WINDOW", offset_to_line(o, starts),
                      items[worst[1]][1][:110],
                      f"локальный участок с долей коротких предложений {worst[0]:.0%} на {STACCATO_WINDOW} подряд")


def scan_verbless(text: str, starts: List[int]) -> Iterable[Finding]:
    """Доля безглагольных предложений наррации.

    Норма арки 1 — 11%. В главах 5-6 было 22-28%: предметы называются,
    но не участвуют в действии. Это и читается как «пустовато».
    """
    items = [(o, s) for o, s in iter_narration_sentences(text) if word_count(s) > 0]
    if len(items) < 60:
        return
    verbless = [1 if not has_verb(s) else 0 for _, s in items]
    ratio = sum(verbless) / len(verbless)
    if ratio > VERBLESS_BLOCK_RATIO:
        sev = "BLOCKER"
        msg = "предметы перечисляются вместо того, чтобы участвовать в действии"
    elif ratio > VERBLESS_WARN_RATIO:
        sev = "WARN"
        msg = "многовато назывных конструкций"
    else:
        return
    yield Finding(sev, "VERBLESS_DENSITY", 1,
                  f"безглагольных предложений наррации {ratio:.0%}",
                  f"{msg}; норма арок 1-2 — 3-7%, порог {VERBLESS_BLOCK_RATIO:.0%}")


def scan_paragraph_fragmentation(text: str, starts: List[int]) -> Iterable[Finding]:
    """Сколько предложений приходится на абзац наррации.

    Норма арки 1 — 2,1. В главе 5 было 3,1 при той же длине абзаца:
    материала столько же, швов в полтора раза больше.
    """
    counts = []
    offset = 0
    worst = None
    for line in text.splitlines(keepends=True):
        if is_prose_line(line) and not is_dialogue_line(line):
            sents = split_sentences(line)
            if sents:
                counts.append(len(sents))
                if len(sents) >= 7 and (worst is None or len(sents) > worst[0]):
                    worst = (len(sents), offset, line.strip()[:120])
        offset += len(line)
    if len(counts) < 25:
        return
    avg = sum(counts) / len(counts)
    if avg > FRAGMENT_BLOCK_RATIO:
        yield Finding("BLOCKER", "PARAGRAPH_FRAGMENTATION", 1,
                      f"в среднем {avg:.1f} предложения на абзац наррации",
                      f"абзацы раздроблены; норма арки 1 — 2,1, порог {FRAGMENT_BLOCK_RATIO}")
    elif avg > FRAGMENT_WARN_RATIO:
        yield Finding("WARN", "PARAGRAPH_FRAGMENTATION", 1,
                      f"в среднем {avg:.1f} предложения на абзац наррации",
                      "абзацы дробнее нормы проекта (2,1)")
    if worst:
        yield Finding("WARN", "FRAGMENTED_PARAGRAPH", offset_to_line(worst[1], starts),
                      worst[2], f"абзац из {worst[0]} предложений — проверить, не опись ли это")


def scan_anaphora(text: str, starts: List[int]) -> Iterable[Finding]:
    offset = 0
    for line in text.splitlines(keepends=True):
        if is_prose_line(line):
            sents = split_sentences(line)
            run: List[str] = []
            run_word = ""
            for s in sents:
                fw = first_word(s)
                short = word_count(s) <= ANAPHORA_MAX_WORDS
                if short and fw and fw == run_word:
                    run.append(s)
                else:
                    if len(run) >= ANAPHORA_MIN_RUN:
                        yield Finding("BLOCKER", "ANAPHORA_RUN", offset_to_line(offset, starts),
                                      " ".join(run)[:140],
                                      f"анафорическая цепочка из {len(run)} коротких фраз с одним зачином — ритмическая тройка")
                    run = [s] if short and fw else []
                    run_word = fw if short else ""
            if len(run) >= ANAPHORA_MIN_RUN:
                yield Finding("BLOCKER", "ANAPHORA_RUN", offset_to_line(offset, starts),
                              " ".join(run)[:140],
                              f"анафорическая цепочка из {len(run)} коротких фраз с одним зачином — ритмическая тройка")
        offset += len(line)


def scan_nominative_chain(text: str, starts: List[int]) -> Iterable[Finding]:
    offset = 0
    for line in text.splitlines(keepends=True):
        if is_prose_line(line) and not is_dialogue_line(line):
            sents = split_sentences(line)
            run: List[str] = []
            for s in sents:
                short = word_count(s) <= NOMINATIVE_MAX_WORDS
                if short and not has_verb(s):
                    tokens = {w.lower() for w in re.findall(r"[А-Яа-яЁё]+", s)}
                    if tokens & PARENTHETICALS:
                        run = []
                        continue
                    run.append(s)
                else:
                    if len(run) >= NOMINATIVE_MIN_RUN:
                        yield Finding("BLOCKER", "NOMINATIVE_CHAIN", offset_to_line(offset, starts),
                                      " ".join(run)[:140],
                                      f"цепочка из {len(run)} безглагольных назывных предложений подряд")
                    run = []
            if len(run) >= NOMINATIVE_MIN_RUN:
                yield Finding("BLOCKER", "NOMINATIVE_CHAIN", offset_to_line(offset, starts),
                              " ".join(run)[:140],
                              f"цепочка из {len(run)} безглагольных назывных предложений подряд")
        offset += len(line)


def scan_repeats(text: str, starts: List[int]) -> Iterable[Finding]:
    total_words = len(re.findall(r"[А-Яа-яЁёA-Za-z]+", text))
    scale = max(1.0, total_words / 10000)

    # 3.1 однообразные атрибуции диалога
    tags = Counter()
    for line in text.splitlines():
        s = line.strip()
        if DIALOGUE_TAG.match(s):
            tags[s.lower()] += 1
    for tag, count in tags.items():
        if count > TAG_LIMIT_PER_10K * scale:
            yield Finding("BLOCKER", "MONOTONE_DIALOGUE_TAG", 1, tag,
                          f"атрибуция повторяется {count} раз на {total_words} слов — диалог ведётся на автопилоте")

    # 3.2 дословные повторы предложений внутри файла
    seen: dict[str, int] = {}
    dupes: dict[str, list[int]] = {}
    offset = 0
    for line in text.splitlines(keepends=True):
        if is_prose_line(line):
            for s in split_sentences(line):
                if word_count(s) < SENTENCE_MIN_WORDS_FOR_DUPE:
                    continue
                key = re.sub(r"\s+", " ", s.lower()).strip()
                if key in seen:
                    dupes.setdefault(key, [seen[key]]).append(offset)
                else:
                    seen[key] = offset
        offset += len(line)
    for key, positions in dupes.items():
        if len(positions) >= 2:
            yield Finding("WARN", "SELF_DUPLICATE", offset_to_line(positions[-1], starts),
                          key[:130],
                          f"предложение повторяется {len(positions)} раз(а) — вероятный след послойной редактуры")


def scan_form(text: str, starts: List[int]) -> Iterable[Finding]:
    paragraphs = re.split(r"\n\s*\n", text)
    offset = 0
    for para in paragraphs:
        stripped = para.strip()
        if stripped and is_prose_line(stripped):
            if len(stripped.split()) == 1 and not stripped.startswith("—"):
                pos = text.find(para, offset)
                yield Finding("WARN", "SINGLE_WORD_PARAGRAPH", offset_to_line(max(pos, 0), starts),
                              stripped, "одиночное слово-абзац; почти всегда подозрительная драматизация")
            lowered = stripped.lower()
            for word in ("словно", "будто"):
                if lowered.count(word) > 1:
                    pos = text.find(para, offset)
                    yield Finding("WARN", f"DENSITY_{word.upper()}", offset_to_line(max(pos, 0), starts),
                                  stripped[:130],
                                  f"`{word}` встречается {lowered.count(word)} раз(а) в одном абзаце")
        offset += len(para) + 2


# ---------------------------------------------------------------------------
# Сентенции в репликах (v2.2)
# ---------------------------------------------------------------------------

# Обобщающий субъект: речь идёт о людях вообще, а не о ком-то в сцене.
SENT_SUBJ = re.compile(
    r"\b(?:люди|человек|человека|человеку|человеком|всякий|каждый|никто|"
    r"тот,\s*кто|те,\s*кто)\b", re.IGNORECASE)

# Гномический презенс: вневременное настоящее время.
SENT_GNOM = re.compile(r"\b\w{3,}(?:ет|ёт|ит|ут|ют|ат|ят|ется|ится|аются|яются)\b")

# Предметный слой. Если он есть, персонаж говорит о деле, а не о жизни вообще,
# и обобщение законно: это регламент, медицина, ремесло.
SENT_DOMAIN = re.compile(
    r"\b(?:метк\w+|контракт\w*|ранг\w*|зон\w+|допуск\w*|отклик\w*|аттестац\w+|"
    r"назначени\w+|гильди\w+|регламент\w*|процедур\w+|учёт\w*|реестр\w*|бланк\w*|"
    r"отчёт\w*|рекомендаци\w+|комисси\w+|нарушени\w+|розыск\w*|повреждени\w+|"
    r"целител\w+|соулс\w*|заряд\w*|причал\w*|мачт\w+|такелаж\w*|полномочи\w+|"
    r"наставлени\w+|выход\w*|шов|швы|рана|ран\w+|жар|бред)\b", re.IGNORECASE)

# Имя собственное — значит, речь о конкретном человеке.
SENT_NAME = re.compile(
    r"\b(?:Гар|Вельт|Кайр\w*|Агнис|Элизабет|Ханн\w+|Лиран\w*|Сигурд\w*|Рэйн\w+|"
    r"Мабрик\w*|Тобер\w*|Торен\w*|Хельг\w+|Варден\w*|Тесс|Ирсал\w+|Минт\w+|"
    r"Арклайт\w*|Северин\w*|Дагоберт\w*|Марн\w+|Ирм\w+|Осс\w+)\b")


def iter_replica_sentences(text: str):
    """Предложения только из реплик: прямая речь и внутренний голос."""
    offset = 0
    for line in text.splitlines(keepends=True):
        s = line.strip()
        if s.startswith("—") or (s.startswith("*") and not s.startswith("**")):
            body = s.strip("*")
            if body.startswith("—"):
                body = body[1:]
            # снять авторскую ремарку вида «— сказал он.»
            body = re.sub(r"\s—\s+[а-яё][^—]*?(?:\.|$)", ". ", body)
            for sent in split_sentences(body):
                yield offset, sent
        offset += len(line)


def scan_sententious(text: str, starts: List[int]) -> Iterable[Finding]:
    """Сентенция: обобщающее суждение о людях, не привязанное к сцене.

    Признак — реплику можно вынуть из главы и повесить на стену, не потеряв
    смысла. Такие фразы звучат умнее говорящего и стирают разницу голосов.
    """
    for off, sent in iter_replica_sentences(text):
        w = word_count(sent)
        if w < 6 or w > 34:
            continue
        if sent.rstrip().endswith("?"):
            continue
        if not SENT_SUBJ.search(sent):
            continue
        if not SENT_GNOM.search(sent):
            continue
        if SENT_DOMAIN.search(sent) or SENT_NAME.search(sent):
            continue
        yield Finding("WARN", "SENTENTIOUS", offset_to_line(off, starts), sent[:130],
                      "обобщение о людях вне предметного слоя; проверить, "
                      "не звучит ли реплика умнее говорящего")


# ---------------------------------------------------------------------------
# Кросс-файловая проверка
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# SEMANTIC_ECHO — смысловой повтор (v2.3)
# ---------------------------------------------------------------------------
#
# Дефект послойной дописки: заход №4 добавляет абзац, не помня, что заход №2
# уже сказал то же самое другими словами. Дословный SELF_DUPLICATE такое
# не ловит — формулировки разные.
#
# Найденный пример (глава 13, кульминация арки 3):
#   «Спина болела так, как болит у человека, который сидит за столом двадцать лет»
#   «Спина. Болела ниже и глубже моего, тем ровным нытьём, которое приходит
#    к человеку, просидевшему за столом полжизни»
#
# Метод: скользящее окно по абзацам наррации, сравнение по множеству
# значимых лемм (грубая нормализация окончаний). Совпадение >= порога
# при достаточной длине — сигнал.

ECHO_WINDOW = 40          # абзацев
ECHO_MIN_CONTENT = 5      # значимых слов в абзаце, иначе не сравниваем
ECHO_JACCARD = 0.42       # доля общих значимых слов

STOPWORDS = {
    "и", "а", "но", "что", "как", "это", "то", "не", "ни", "же", "бы", "ли",
    "в", "во", "на", "с", "со", "к", "ко", "по", "за", "из", "от", "до", "у",
    "о", "об", "для", "при", "про", "над", "под", "без", "через", "потому",
    "который", "которая", "которое", "которые", "которых", "которым",
    "я", "ты", "он", "она", "оно", "они", "мы", "вы", "меня", "тебя", "его",
    "её", "их", "мне", "тебе", "ему", "ей", "им", "себя", "себе", "свой",
    "своя", "своё", "свои", "мой", "моя", "моё", "мои", "был", "была", "было",
    "были", "быть", "есть", "уже", "ещё", "только", "даже", "вот", "так",
    "там", "тут", "здесь", "тогда", "потом", "очень", "всё", "все", "весь",
    "если", "чтобы", "когда", "где", "куда", "чем", "чём", "тем", "том",
    "этот", "эта", "эти", "того", "этого", "этом", "этой", "нет", "да",
}


def _norm_word(w: str) -> str:
    """Грубая нормализация: срезаем частые окончания."""
    w = w.lower()
    for suf in ("ами", "ями", "ого", "его", "ому", "ему", "ыми", "ими",
                "ых", "их", "ов", "ев", "ам", "ям", "ах", "ях", "ой", "ей",
                "ую", "юю", "ые", "ие", "ый", "ий", "ая", "яя", "ое", "ее",
                "ла", "ло", "ли", "ть", "ет", "ёт", "ит", "ут", "ют", "ат",
                "ят", "у", "ю", "а", "я", "о", "е", "ы", "и", "ь"):
        if len(w) > 5 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _content_words(text: str) -> set:
    words = re.findall(r"[А-Яа-яЁё]{3,}", text.lower())
    return {_norm_word(w) for w in words if w not in STOPWORDS}


def scan_semantic_echo(text: str, starts: List[int]) -> Iterable[Finding]:
    """Абзацы наррации, повторяющие друг друга по смыслу."""
    paras = []
    offset = 0
    for raw in re.split(r"(\n\s*\n)", text):
        if raw.strip() and not raw.strip().startswith(("#", "---")):
            s = raw.strip()
            if not s.startswith(("—", "*", "«", "|")):
                cw = _content_words(s)
                if len(cw) >= ECHO_MIN_CONTENT:
                    paras.append((offset, s, cw))
        offset += len(raw)

    reported = set()
    for i in range(len(paras)):
        o1, t1, w1 = paras[i]
        for j in range(i + 1, min(i + 1 + ECHO_WINDOW, len(paras))):
            o2, t2, w2 = paras[j]
            inter = len(w1 & w2)
            union = len(w1 | w2)
            if union == 0:
                continue
            jac = inter / union
            if jac >= ECHO_JACCARD and inter >= 4:
                key = (min(o1, o2), max(o1, o2))
                if key in reported:
                    continue
                reported.add(key)
                yield Finding(
                    "WARN", "SEMANTIC_ECHO", offset_to_line(o2, starts),
                    f"«{t1[:70]}…» ≈ «{t2[:70]}…»",
                    f"абзацы совпадают на {jac:.0%} значимых слов "
                    f"(строки {offset_to_line(o1, starts)} и "
                    f"{offset_to_line(o2, starts)}) — вероятный след "
                    f"послойной дописки")


def cross_file_duplicates(paths: List[Path]) -> List[str]:
    """Ищет дословные предложения, общие для разных глав."""
    per_file = {}
    for p in paths:
        text = p.read_text(encoding="utf-8")
        acc = set()
        for line in text.splitlines():
            if is_prose_line(line):
                for s in split_sentences(line):
                    if word_count(s) >= 5:
                        acc.add(re.sub(r"\s+", " ", s.lower()).strip())
        per_file[p] = acc
    report: List[str] = []
    names = list(per_file)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            common = per_file[names[i]] & per_file[names[j]]
            for s in sorted(common, key=len, reverse=True)[:12]:
                report.append(f"{names[i].name} <-> {names[j].name}: {s[:110]}")
    return report


# ---------------------------------------------------------------------------
# Запуск
# ---------------------------------------------------------------------------


def run_guard(path: Path) -> List[Finding]:
    text = path.read_text(encoding="utf-8")
    starts = build_line_index(text)
    findings: List[Finding] = []
    findings.extend(scan_lexical(text, starts))
    findings.extend(scan_staccato(text, starts))
    findings.extend(scan_verbless(text, starts))
    findings.extend(scan_paragraph_fragmentation(text, starts))
    findings.extend(scan_anaphora(text, starts))
    findings.extend(scan_nominative_chain(text, starts))
    findings.extend(scan_repeats(text, starts))
    findings.extend(scan_form(text, starts))
    findings.extend(scan_sententious(text, starts))
    findings.extend(scan_semantic_echo(text, starts))
    findings.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.line, f.code))
    return findings


def print_findings(path: Path, findings: List[Finding]) -> None:
    print(f"\n=== {path} ===")
    if not findings:
        print("OK: блокеров и предупреждений не найдено")
        return
    for f in findings:
        print(f"[{f.severity}] {f.code} @ line {f.line}: {f.message}")
        print(f"    {f.excerpt}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Guard художественной прозы проекта shardsoftheabyss (v2: лексика + ритм + самоповтор)")
    parser.add_argument("paths", nargs="+", help="файлы для проверки")
    parser.add_argument("--cross", action="store_true",
                        help="дополнительно искать дословные совпадения между указанными файлами")
    parser.add_argument("--quiet", action="store_true", help="печатать только сводку")
    args = parser.parse_args(argv)

    all_findings: List[Finding] = []
    paths: List[Path] = []
    for raw in args.paths:
        path = Path(raw)
        if not path.exists():
            print(f"ERROR: file not found: {path}", file=sys.stderr)
            return 2
        paths.append(path)
        findings = run_guard(path)
        if not args.quiet:
            print_findings(path, findings)
        all_findings.extend(findings)

    if args.cross and len(paths) > 1:
        print("\n=== кросс-файловые дословные повторы ===")
        rep = cross_file_duplicates(paths)
        if not rep:
            print("OK: пересечений не найдено")
        for line in rep:
            print("  " + line)

    blockers = [f for f in all_findings if f.severity == "BLOCKER"]
    warns = [f for f in all_findings if f.severity == "WARN"]

    print("\n--- summary ---")
    print(f"blockers: {len(blockers)}")
    print(f"warnings: {len(warns)}")
    if blockers:
        by_code = Counter(f.code for f in blockers)
        print("по кодам: " + ", ".join(f"{c}={n}" for c, n in by_code.most_common()))

    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
