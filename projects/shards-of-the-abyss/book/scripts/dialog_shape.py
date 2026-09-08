#!/usr/bin/env python3
"""Форма диалога: то, что делает главу «шаблонной» независимо от словаря.

Появился при разборе главы 1 (сентябрь 2026). Автор: «к концу второй главы
я уже все диалоги наизусть понимаю, как строятся». Разбор показал, что шаблон
живёт не в словах, а в форме:

  1. реплика-выпад / реплика-парирование по 2–4 слова, сериями;
  2. каждая диалоговая сцена закрывается абзацем, где POV выносит вердикт
     («и это было хуже, чем если бы…», «у меня всегда так…»);
  3. взрослые заканчивают разговор одинаковым императивом-заботой
     («Ешь», «Иди», «Зашей», «Одевайся»);
  4. один и тот же жест-заполнитель у разных людей («дольше, чем нужно»,
     «тем же голосом», «не оборачиваясь», «пожал плечом»).

Ни один из старых скриптов этого не считал: style_guard смотрит на ритм
наррации, tics — на обороты, voice_stats — на длину реплик по говорящим.
Этот считает форму сцены.

Запуск:
    python3 scripts/dialog_shape.py 03-manuscript/arc-01/ch-01.md
    python3 scripts/dialog_shape.py --verbose 03-manuscript/arc-01/ch-01.md
    python3 scripts/dialog_shape.py 03-manuscript/arc-*/ch-*.md   # таблица

Числа — не норма, а ориентир. Решение принимает человек.
"""

from __future__ import annotations

import argparse
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

# ---------------------------------------------------------------------------
# Разбор
# ---------------------------------------------------------------------------

SPEECH_VERBS = (
    r"сказал|спросил|ответил|отозвал|повторил|продолжа|согласил|добавил|"
    r"уточнил|заметил|перебил|бросил|проговорил|усмехнул|кивнул|пожал|"
    r"посмотрел|поставил|подвинул|придвинул|закрыл|сложил|поправил|показал|"
    r"перехват|подышал|надел|обернул|отхлебнул|допил|вернул|встал|сел|"
    r"подвину|переложи|фыркну|хмыкну|вздохну|покача"
)


def paragraphs(text: str) -> list[str]:
    out = []
    for p in text.split("\n\n"):
        p = p.strip()
        if not p or p.startswith("#"):
            continue
        out.append(p)
    return out


def is_reply(p: str) -> bool:
    return p.startswith("—")


def speech_words(p: str) -> int:
    """Слова прямой речи без атрибуции (грубо: нечётные сегменты после ' — ')."""
    segs = re.split(r"\s—\s", p[1:].strip())
    spoken = []
    for i, s in enumerate(segs):
        if i % 2 == 1 and re.search(SPEECH_VERBS, s):
            continue
        spoken.append(s)
    return len(re.findall(r"[А-Яа-яЁё]+", " ".join(spoken)))


# Закрывающий вердикт POV: абзац после последней реплики сцены, в котором
# героиня объясняет, как это понимать.
VERDICT = re.compile(
    r"(всегда так|каждый раз|у меня всегда|так у нас|так у меня|вообще редко|"
    r"вообще никогда|^Это был[аои]? |хуже, чем если|неприятнее, чем если|"
    r"и за это я|за это я е[её]|Тем же голосом|это оказалось|"
    r"это было (хуже|лучше|правд|точн|слишком)|"
    r"наизусть|слишком точно|Это была не |Это было не )",
    re.IGNORECASE | re.MULTILINE,
)

# Императив-прощание: последняя реплика сцены — короткий приказ.
IMPERATIVE_CLOSER = re.compile(
    r"^— (Иди|Идите|Ешь|Ешьте|Одевайся|Зашей|Набирай|Молчи и бери|Садись|"
    r"Сядь|Спи|Ложись|Пей|Бери|Возьми|Ступай|Ступайте|Пошли|Пойдём|Идём|"
    r"Иди уже|Садись уже|Подложи|Держи|Отдай|Молчи)\b"
)

# Жесты-заполнители, которые кочуют от персонажа к персонажу.
GESTURES = {
    "дольше, чем (нужно/требовалось/следует)": r"дольше, чем",
    "ровно столько, сколько": r"ровно столько, сколько",
    "хуже/неприятнее, чем если бы": r"(хуже|неприятнее|лучше), чем если",
    "тем же голосом": r"[Тт]ем же голосом",
    "не оборачиваясь / не поднимая головы / не глядя": r"не оборачиваясь|не поднима\w+ голов|не глядя|не отрываясь",
    "пожал(а) плечом": r"пожал\w* плеч",
    "усмехнул(ась)": r"усмехнул",
    "будто / как будто": r"\bбудто\b",
    "«— Знаю.» / «— Я знаю.»": r"^— (Я )?[Зз]наю\.$",
    "одиночное «— Почему?/Зачем?/Что?»": r"^— (Почему|Зачем|Что|Куда|Кого|Какой|Чем|Когда|Кто)\?$",
    "и я (только потом) поняла/сообразила": r"\bя (поняла|сообразила|не сразу поняла|только потом сообразила)",
    "задержал(а) взгляд": r"задержал\w* (на мне |на нём |на ней )?взгляд",
}


def scenes(paras: list[str]):
    """Диалоговые сцены: блоки, где реплики идут подряд, разделённые
    короткой наррацией (< 40 слов). Возвращает (реплики, последняя реплика,
    закрывающий абзац)."""
    i = 0
    n = len(paras)
    while i < n:
        if not is_reply(paras[i]):
            i += 1
            continue
        j = i
        replies = []
        while j < n and (
            is_reply(paras[j])
            or (j + 1 < n and is_reply(paras[j + 1]) and len(paras[j].split()) < 40)
        ):
            if is_reply(paras[j]):
                replies.append(paras[j])
            j += 1
        closer = paras[j] if j < n else ""
        yield replies, closer
        i = j + 1


def analyze(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    paras = paragraphs(text)
    replies = [p for p in paras if is_reply(p)]
    lengths = [speech_words(p) for p in replies] or [0]

    # серии коротких реплик подряд
    runs = []
    cur = 0
    for p in paras:
        if is_reply(p) and speech_words(p) <= 4:
            cur += 1
        else:
            if cur >= 4:
                runs.append(cur)
            cur = 0
    if cur >= 4:
        runs.append(cur)

    sc_total = sc_verdict = sc_imper = 0
    verdicts = []
    impers = []
    for reps, closer in scenes(paras):
        if len(reps) < 6:
            continue
        sc_total += 1
        if closer and VERDICT.search(closer):
            sc_verdict += 1
            verdicts.append(closer[:140])
        if IMPERATIVE_CLOSER.match(reps[-1]):
            sc_imper += 1
            impers.append(reps[-1][:80])

    gestures = {k: len(re.findall(v, text, re.MULTILINE)) for k, v in GESTURES.items()}

    return {
        "file": str(path),
        "words": len(re.findall(r"[А-Яа-яЁё]+", text)),
        "replies": len(replies),
        "median": statistics.median(lengths),
        "short3": sum(1 for x in lengths if x <= 3) / len(lengths),
        "short6": sum(1 for x in lengths if x <= 6) / len(lengths),
        "runs": runs,
        "scenes": sc_total,
        "verdict": sc_verdict,
        "verdict_list": verdicts,
        "imper": sc_imper,
        "imper_list": impers,
        "gestures": gestures,
    }


# ---------------------------------------------------------------------------
# Вывод
# ---------------------------------------------------------------------------

def print_one(r: dict, verbose: bool) -> None:
    print(f"=== {r['file']} ===")
    print(f"слов {r['words']}, реплик {r['replies']}, медиана реплики {r['median']:.0f} слов")
    print(f"реплик ≤3 слов: {r['short3']:.0%}   ≤6 слов: {r['short6']:.0%}")
    print(f"серий из ≥4 коротких реплик подряд: {len(r['runs'])} {r['runs']}")
    print(f"диалоговых сцен (≥6 реплик): {r['scenes']}; закрыто вердиктом POV: {r['verdict']}; "
          f"закрыто императивом: {r['imper']}")
    hot = {k: v for k, v in r["gestures"].items() if v}
    if hot:
        print("жесты-заполнители:")
        for k, v in sorted(hot.items(), key=lambda kv: -kv[1]):
            print(f"  {v:3d}  {k}")
    if verbose:
        if r["verdict_list"]:
            print("--- закрывающие вердикты:")
            for v in r["verdict_list"]:
                print("   ·", v)
        if r["imper_list"]:
            print("--- императивы-прощания:")
            for v in r["imper_list"]:
                print("   ·", v)
    print()


def print_table(rows: list[dict]) -> None:
    print(f"{'файл':30s} {'слов':>6} {'репл':>5} {'≤3сл':>5} {'серии':>5} {'сцен':>4} {'верд':>4} {'импер':>5} {'жесты':>5}")
    for r in rows:
        name = Path(r["file"]).name
        g = sum(r["gestures"].values())
        print(f"{name:30s} {r['words']:6d} {r['replies']:5d} {r['short3']:5.0%} {len(r['runs']):5d} "
              f"{r['scenes']:4d} {r['verdict']:4d} {r['imper']:5d} {g:5d}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--verbose", "-v", action="store_true", help="показать закрывающие вердикты и императивы")
    args = ap.parse_args()

    rows = [analyze(Path(f)) for f in args.files]
    if len(rows) == 1:
        print_one(rows[0], args.verbose)
    else:
        print_table(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
