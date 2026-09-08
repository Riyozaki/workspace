#!/usr/bin/env python3
"""Замеры голосов: длина реплик по говорящим.

Существует потому, что норма «доля Тени ≥12% объёма главы» была выполнена
во всех главах арки 3 — и Тень при этом провалилась как персонаж.
Числовая норма ловит отсутствие, но не ловит невыразительность.

Ключевой замер — средняя длина реплики Тени. Ориентир (Джонни Сильверхенд)
предполагает, что она огрызается: норма ≤7 слов. Замер по написанному
дал 9,1 — самый многословный персонаж книги.

Использование:
    python3 scripts/voice_stats.py 03-manuscript/arc-03/ch-11.md
    python3 scripts/voice_stats.py --long 03-manuscript/arc-03/ch-11.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SHADOW_MAX_AVG = 7.0
SHADOW_MIN_SHARE = 0.115  # 12% с допуском на округление

# Арка 2 — становление контакта: Тень появляется в гл. 6 и первые главы
# молчит по сюжету, доля физически не может дойти до 12%. Норма рассчитана
# на арки 3-5, где контакт уже установлен. Порог доли здесь не применяется,
# порог длины реплики (не лектор) действует всегда.
SHARE_EXEMPT = {"ch-06.md", "ch-07.md", "ch-08.md", "ch-09.md", "ch-10.md"}

# Гл. 34 целиком происходит внутри души: речи вслух там нет физически,
# и норма «средняя реплика вслух ≥4» к ней неприменима.
# Гл. 35 — обратный случай: внешняя глава, где Тень держится в тени
# намеренно (Сильвия заново собирает себя среди людей).
NO_SPOKEN = {"ch-34.md"}
FINALE_EXEMPT = {"ch-35.md"}
SILVIA_MIN_AVG = 4.0

TAG = re.compile(r"\s—\s+[а-яё][^—]*?(?:\.|$)")


def words(s: str) -> int:
    return len(re.findall(r"[\w-]+", s))


ITALIC = re.compile(r"\*([^*]+)\*")


def collect(text: str):
    shadow, spoken = [], []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("*") and not s.startswith("**"):
            # Реплика Тени может быть разорвана ремаркой автора:
            #   *Всё,* — сказала она. — *Я в этом теле нахожусь.*
            # Считаем только курсивные сегменты, ремарку выбрасываем.
            segs = ITALIC.findall(s)
            body = " ".join(segs) if segs else TAG.sub(" ", s.strip("*"))
            if words(body):
                shadow.append(body.strip())
        elif s.startswith("—"):
            body = TAG.sub(" ", s[1:])
            if words(body):
                spoken.append(body.strip())
    return shadow, spoken


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Замеры голосов")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--long", action="store_true",
                    help="показать самые длинные реплики Тени")
    args = ap.parse_args(argv)

    fail = 0
    print(f"{'файл':12} {'слов':>6} {'Тень%':>6} {'Тень ср':>8} "
          f"{'реплик':>7} {'вслух ср':>9}")

    for raw in args.paths:
        p = Path(raw)
        if not p.exists():
            print(f"ERROR: нет файла {p}", file=sys.stderr)
            return 2
        t = p.read_text(encoding="utf-8")
        total = words(t)
        shadow, spoken = collect(t)

        sh_words = sum(words(x) for x in shadow)
        share = sh_words / max(total, 1)
        sh_avg = sh_words / max(len(shadow), 1)
        sp_avg = sum(words(x) for x in spoken) / max(len(spoken), 1)

        flags = ""
        if shadow:
            # округление: 7.04 печатается как «7.0» и выглядит нормой
            if round(sh_avg, 1) > SHADOW_MAX_AVG:
                flags += " ❌длинно"
                fail += 1
            if share < SHADOW_MIN_SHARE:
                if p.name in SHARE_EXEMPT:
                    flags += "  (арка 2: контакт только устанавливается)"
                elif p.name in FINALE_EXEMPT:
                    flags += "  (финал: Сильвия среди людей, Тень в тени)"
                else:
                    flags += " ❌мало"
                    fail += 1
        if sp_avg < SILVIA_MIN_AVG and p.name not in NO_SPOKEN:
            flags += " ❌реплики коротки"
            fail += 1

        print(f"{p.name:12} {total:6} {share:5.0%} {sh_avg:8.1f} "
              f"{len(shadow):7} {sp_avg:9.1f}{flags}")

        if args.long and shadow:
            print("   самые длинные реплики Тени:")
            for x in sorted(shadow, key=words, reverse=True)[:6]:
                print(f"     [{words(x):2}] {x[:96]}")

    print(f"\nнормы: Тень ср ≤{SHADOW_MAX_AVG} сл., доля ≥{SHADOW_MIN_SHARE:.0%}, "
          f"реплики вслух ср ≥{SILVIA_MIN_AVG}")
    print(f"\n--- итог ---\nнарушений: {fail}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
