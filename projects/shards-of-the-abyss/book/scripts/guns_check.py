#!/usr/bin/env python3
"""Проверка реестра ружей: не молчит ли ружьё дольше допустимого.

Причина существования: вторая печать с пакета молчала 11 глав подряд,
и это заметили только при сплошном ревью книги. План арки честно писал
«молчит, ждёт» — но у статуса «ждёт» не было срока годности.

Скрипт читает 03-manuscript/GUNS.md, берёт колонки «Заряжено» и
«Последнее упоминание», сравнивает с номером последней написанной главы
и сообщает, что просрочено.

Использование:
    python3 scripts/guns_check.py
    python3 scripts/guns_check.py --current 14
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

GUNS_PATH = Path("03-manuscript/GUNS.md")
MANUSCRIPT = Path("03-manuscript")
SILENCE_LIMIT = 5  # глав


def last_written_chapter() -> int:
    nums = []
    for p in MANUSCRIPT.glob("arc-*/ch-*.md"):
        m = re.search(r"ch-(\d+)", p.name)
        if m:
            nums.append(int(m.group(1)))
    return max(nums) if nums else 0


def parse_chapter(cell: str):
    """Из «гл. 12 (стол с документами)» вытащить 12."""
    m = re.search(r"гл\.?\s*(\d+)", cell)
    return int(m.group(1)) if m else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Проверка реестра ружей")
    ap.add_argument("--current", type=int, default=None,
                    help="номер текущей главы (по умолчанию — последняя написанная)")
    ap.add_argument("--path", default=str(GUNS_PATH))
    args = ap.parse_args(argv)

    path = Path(args.path)
    if not path.exists():
        print(f"ERROR: нет реестра {path}", file=sys.stderr)
        return 2

    current = args.current or last_written_chapter()
    print(f"Текущая глава: {current}. Предел молчания: {SILENCE_LIMIT} глав.\n")

    overdue, watch, paused, ok, done = [], [], [], 0, 0

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        name = cells[0]
        if name.startswith("**Ружьё") or name == "Ружьё" or not name:
            continue
        status = cells[-1]
        if "✅" in status:
            done += 1
            continue
        if "⚫" in status:
            continue
        if "⏸" in status:
            # Отложено решением автора: ружьё держат до конкретной сцены.
            # Обязателен комментарий в колонке «Выстрел» с номером главы.
            paused.append((name, cells[3]))
            continue

        last = parse_chapter(cells[2])
        if last is None:
            continue
        silence = current - last
        clean = re.sub(r"\*\*", "", name)[:52]
        if silence > SILENCE_LIMIT:
            overdue.append((silence, clean, last))
        elif silence >= 3:
            watch.append((silence, clean, last))
        else:
            ok += 1

    if overdue:
        print("🔴 ПРОСРОЧЕНО — нужно напоминание или разрядка:")
        for s, n, last in sorted(overdue, reverse=True):
            print(f"   молчит {s} глав (с гл. {last}): {n}")
        print()
    if watch:
        print("🟡 Следить:")
        for s, n, last in sorted(watch, reverse=True):
            print(f"   молчит {s} глав (с гл. {last}): {n}")
        print()

    if paused:
        print("⏸ отложено решением автора:")
        for name, when in paused:
            print(f"   {name[:58]} → {when}")
        print()

    print(f"🟢 в порядке: {ok}   ✅ выстрелило: {done}   ⏸ отложено: {len(paused)}")
    print(f"\n--- итог ---\nпросрочено: {len(overdue)}")
    return 1 if overdue else 0


if __name__ == "__main__":
    raise SystemExit(main())
