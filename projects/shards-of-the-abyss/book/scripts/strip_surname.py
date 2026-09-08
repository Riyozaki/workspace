#!/usr/bin/env python3
"""Снятие фамилии «Дюваль» по решению автора (август 2026).

У Сильвии, Элизабет и Агнис фамилии нет вообще. Слово «Дюваль» уходит
из книги полностью.

Главный принцип, взятый из HARD-BLOCKERS §1.11: обращение по фамилии
выродилось в **затычку** — способ начать реплику, не думая над первым
словом. Поэтому основная операция здесь — не замена, а **снятие**:
живая речь обращениями не сорит.

Классы обработки:

  DROP_OPEN    «— Дюваль, ты...»      → «— Ты...»          (снять, поднять регистр)
  DROP_DASH    «— Дюваль. Как рука?»  → «— Как рука?»      (снять)
  DROP_MID     «..., Дюваль, ...»     → «..., ...»          (снять запятые-вокатив)
  DROP_END     «..., Дюваль.»         → «...»               (снять)
  CALL         «— Дюваль!»            → «— Сильвия!»        (оклик: имя работает)
  DOC          «Дюваль С.»            → переписывается вручную (документы)
  FAMILY       «Элизабет Дюваль»      → «Элизабет»          (фамилии нет)

Строки класса DOC и одиночные реплики «— Дюваль.» скрипт **не трогает**:
там нужно решение человека, потому что снятие оставит обрубок.

Запуск:
    python3 scripts/strip_surname.py --dry-run 03-manuscript/arc-*/ch-*.md
    python3 scripts/strip_surname.py --apply 03-manuscript/arc-*/ch-*.md
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

NAME = "Дюваль"


def cap(s: str) -> str:
    """Поднять регистр первой буквы, не трогая остальное."""
    for i, ch in enumerate(s):
        if ch.isalpha():
            return s[:i] + ch.upper() + s[i + 1:]
        if ch not in " \t«\"'—*":
            return s
    return s


def process_line(line: str):
    """Возвращает (новая_строка, список_кодов). Пустой список = не тронуто."""
    codes = []
    out = line

    # --- FAMILY: «Элизабет Дюваль», «Агнис Дюваль», «Сильвия Дюваль» -------
    new = re.sub(r"\b(Элизабет|Агнис|Сильвия)\s+" + NAME + r"\b", r"\1", out)
    if new != out:
        codes.append("FAMILY")
        out = new

    if NAME not in out:
        return out, codes

    # --- DOC: инициалы и документы — не трогаем автоматически --------------
    if re.search(NAME + r"\s+[САЭA-Z]\.|[САЭ]\.\s*" + NAME, out):
        codes.append("DOC_SKIP")
        return out, codes

    # --- CALL: оклик «— Дюваль!» / «— Дюваль?» -----------------------------
    new = re.sub(r"(^|—\s*|\*)" + NAME + r"(?=[!?])", r"\1Сильвия", out)
    if new != out:
        codes.append("CALL")
        out = new

    if NAME not in out:
        return out, codes

    # --- одиночная реплика «— Дюваль.» — оставляем человеку ----------------
    if re.match(r"^\s*[—*]?\s*" + NAME + r"\.?\*?\s*$", out.strip()):
        codes.append("SOLO_SKIP")
        return out, codes

    # --- ATTRIB: «— Дюваль, — сказал он.» ---------------------------------
    # Здесь реплика состоит из одного обращения, а дальше идут слова автора.
    # Снять обращение нельзя — останется «— — сказал он». Такие места
    # требуют решения человека: либо реплика получает содержание, либо
    # выкидывается вместе с атрибуцией.
    #
    # Речь Тени оформляется курсивом, поэтому та же реплика выглядит как
    # «*Дюваль,* — сказала она»: закрывающая звёздочка стоит до тире.
    if re.match(r"^\s*[—*]\s*" + NAME + r"\s*,\s*\*?\s*—", out):
        codes.append("ATTRIB_SKIP")
        return out, codes

    # --- DROP_OPEN: «— Дюваль, ты...» → «— Ты...» --------------------------
    m = re.match(r"^(\s*[—*]\s*)" + NAME + r",\s*(.+)$", out, re.DOTALL)
    if m:
        out = m.group(1) + cap(m.group(2))
        codes.append("DROP_OPEN")
        return out, codes

    # --- DROP_DASH: «— Дюваль. Как рука?» → «— Как рука?» ------------------
    # Но не когда следом идут слова автора («— Дюваль. — Он сложил лист.»):
    # там снятие оставит «— — Он сложил лист».
    m = re.match(r"^(\s*[—*]\s*)" + NAME + r"\.\s+(.+)$", out, re.DOTALL)
    if m and not m.group(2).lstrip().startswith("—"):
        out = m.group(1) + cap(m.group(2))
        codes.append("DROP_DASH")
        return out, codes
    if m:
        codes.append("ATTRIB_SKIP")
        return out, codes

    # --- LIST: перечисление имён -------------------------------------------
    # «Райгар, Тавия, Рэйна, Дюваль» — здесь фамилия несёт человека, а не
    # обращение. Снятие вычеркнуло бы Сильвию из состава отряда.
    OTHER = (r"Акацуки|Райгар|Тавия|Рэйна|Вигга|Мейр|Норд|Тэсс|Могила|"
             r"Кассандра|Сигурд|Мабрик|Марна|Ханна|Лиран")
    if re.search(r"(?:" + OTHER + r")\s*,\s*" + NAME, out) or \
       re.search(NAME + r"\s*,\s*(?:" + OTHER + r")", out):
        codes.append("LIST_SKIP")
        return out, codes

    # --- DROP_MID: «..., Дюваль, ...» --------------------------------------
    new = re.sub(r",\s*" + NAME + r",", ",", out)
    if new != out:
        codes.append("DROP_MID")
        out = new

    # --- DROP_END: «..., Дюваль.» / «..., Дюваль!» -------------------------
    new = re.sub(r",\s*" + NAME + r"(?=[.!?*])", "", out)
    if new != out:
        codes.append("DROP_END")
        out = new

    # --- вокатив в середине реплики после тире: «— ..., Дюваль» ------------
    new = re.sub(r",\s*" + NAME + r"\b", "", out)
    if new != out:
        codes.append("DROP_TAIL")
        out = new

    return out, codes


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if not args.apply and not args.dry_run:
        args.dry_run = True

    stats = Counter()
    leftovers = []

    for p in [Path(x) for x in args.paths]:
        text = p.read_text(encoding="utf-8")
        if NAME not in text:
            continue
        lines = text.split("\n")
        changed = False
        for i, line in enumerate(lines):
            if NAME not in line:
                continue
            new, codes = process_line(line)
            for c in codes:
                stats[c] += 1
            if new != line:
                changed = True
                lines[i] = new
                if args.dry_run:
                    print(f"{p.name}:{i+1} [{'/'.join(codes)}]")
                    print(f"  - {line.strip()[:150]}")
                    print(f"  + {new.strip()[:150]}")
            if NAME in new:
                leftovers.append((p.name, i + 1, new.strip()[:130], "/".join(codes)))
        if changed and args.apply:
            p.write_text("\n".join(lines), encoding="utf-8")

    print("\n--- сводка операций ---")
    for k, v in stats.most_common():
        print(f"{k:<12} {v}")

    print(f"\n--- осталось вручную: {len(leftovers)} ---")
    for name, ln, txt, codes in leftovers:
        print(f"{name}:{ln} [{codes}] {txt}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
