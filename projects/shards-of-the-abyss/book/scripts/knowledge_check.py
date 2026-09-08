#!/usr/bin/env python3
"""Проверка непрерывности знания персонажа.

Ловит дефект, который не видит style_guard: POV использует факт
раньше, чем узнаёт его из текста.

Пример из главы 6:
    «Правое бедро отзывалось тупо и ровно, потому что я двенадцать
     дней пролежала на нём.»
стояло за 3000 знаков ДО того, как Ханна назвала срок.

Использование:
    python3 scripts/knowledge_check.py <файл> --fact "двенадцат" --learned "— Двенадцать дней."
    python3 scripts/knowledge_check.py <файл> --auto
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# Факты, которые почти всегда требуют проверки. Каждый — (метка, паттерн упоминания).
AUTO_FACTS = [
    ("срок без сознания", r"двенадцат\w*\s+дн"),
    ("название гильдии", r"«Феникс»|Фениксов|гильди\w+ «"),
    ("имя Тень", r"\bТень\b|\bТени\b|\bТенью\b"),
    ("контрактная метка", r"контрактн\w+ метк|метк[аиуе]\b"),
    ("имя Ханна", r"\bХанн[аеуы]\b"),
    ("имя Лиран", r"\bЛиран\w*\b"),
    ("имя Ирсаль", r"\bИрсал\w+\b"),
    ("имя Сигурд", r"\bСигурд\w*\b"),
    ("имя Рэйна", r"\bРэйн[аеуы]\b"),
    ("ранг", r"\bвтор\w+ ранг|перв\w+ ранг|трет\w+ ранг"),
]

# Латиница в русской прозе — почти всегда случайная вставка при правке.
LATIN = re.compile(r"\b[A-Za-z]{2,}\b")


def find_first(text: str, pattern: str) -> int:
    m = re.search(pattern, text, re.IGNORECASE)
    return m.start() if m else -1


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def excerpt(text: str, pos: int, width: int = 110) -> str:
    s = max(0, pos - 40)
    e = min(len(text), pos + width)
    return text[s:e].replace("\n", " ").strip()


def check_fact(text: str, label: str, mention: str, learned: str | None) -> list[str]:
    """Возвращает список проблем."""
    problems = []
    first = find_first(text, mention)
    if first < 0:
        return problems

    if learned:
        learn_pos = text.find(learned)
        if learn_pos < 0:
            problems.append(f"[?] {label}: маркер узнавания не найден в тексте")
            return problems
        if first < learn_pos:
            problems.append(
                f"[!] {label}: упомянут в строке {line_of(text, first)}, "
                f"а узнан только в строке {line_of(text, learn_pos)}\n"
                f"    {excerpt(text, first)}"
            )
    return problems


def auto_report(text: str, path: Path) -> int:
    """Печатает первое упоминание каждого известного факта.

    Автоматически определить момент узнавания нельзя — это делает человек.
    Задача режима: показать, где искать.
    """
    print(f"\n=== {path} — первые упоминания ключевых фактов ===")
    found = 0
    for label, pattern in AUTO_FACTS:
        pos = find_first(text, pattern)
        if pos >= 0:
            found += 1
            print(f"\n  {label} — строка {line_of(text, pos)}")
            print(f"    {excerpt(text, pos)}")
    if not found:
        print("  ключевых фактов не найдено")
    print("\n  Проверьте вручную: знает ли POV каждый факт в момент первого упоминания.")
    return found


def check_latin(text: str, path: Path) -> int:
    hits = list(LATIN.finditer(text))
    if not hits:
        return 0
    print(f"\n=== {path} — латиница в русском тексте ===")
    for m in hits:
        print(f"  [!] строка {line_of(text, m.start())}: {m.group(0)}")
        print(f"      {excerpt(text, m.start())}")
    return len(hits)


def check_repeats_nearby(text: str, path: Path, window: int = 600) -> int:
    """Повтор редкого слова в пределах окна — след послойной правки."""
    words = [(m.group(0).lower(), m.start())
             for m in re.finditer(r"\b[А-Яа-яЁё]{6,}\b", text)]
    seen: dict[str, int] = {}
    problems = 0
    for w, pos in words:
        if w in seen and pos - seen[w] < window:
            print(f"  [~] строка {line_of(text, pos)}: «{w}» повторяется через "
                  f"{pos - seen[w]} знаков")
            problems += 1
        seen[w] = pos
    if problems:
        print(f"\n=== {path} — близкие повторы ===")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Проверка непрерывности знания персонажа")
    ap.add_argument("path")
    ap.add_argument("--fact", help="паттерн упоминания факта")
    ap.add_argument("--learned", help="точная строка, где POV узнаёт факт")
    ap.add_argument("--auto", action="store_true", help="показать первые упоминания ключевых фактов")
    ap.add_argument("--latin", action="store_true", help="искать латиницу")
    args = ap.parse_args(argv)

    path = Path(args.path)
    if not path.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 2
    text = path.read_text(encoding="utf-8")

    problems = 0

    if args.fact:
        found = check_fact(text, args.fact, args.fact, args.learned)
        for p in found:
            print(p)
        problems += len(found)

    if args.auto or not args.fact:
        auto_report(text, path)

    problems += check_latin(text, path)

    if problems:
        print(f"\n--- найдено проблем: {problems} ---")
        return 1
    print("\n--- автоматических проблем не найдено ---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
