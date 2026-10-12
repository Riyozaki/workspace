# -*- coding: utf-8 -*-

with open("chapter_8.md", "r", encoding="utf-8") as f:
    text = f.read()

import re

# 1. пятой ступени -> третьей ступени
text = text.replace("пятой ступени", "третьей ступени")

# 2. таймер декад
text = text.replace("менее десяти декад", "меньше восьми декад")

# 3. пять лет онемения -> два года
for m in re.finditer(r'.{0,50}\bпять\s+лет\b.{0,50}', text):
    print("ch8 5 years:", m.group(0))

text = text.replace("впервые за пять лет оцепенения", "впервые за два года оцепенения")
text = text.replace("пять лет назад заключивший договор", "два года назад заключивший договор")
text = text.replace("пять лет мертвого покоя", "два года мертвого покоя")

# Check Бездна / Пустота in Krev scene
for m in re.finditer(r'.{0,50}\b(?:Бездна|Пустота|Бездны|Пустоты)\b.{0,50}', text):
    print("ch8 Krev void:", m.group(0))

with open("chapter_8.md", "w", encoding="utf-8") as f:
    f.write(text)

