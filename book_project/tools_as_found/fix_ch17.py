# -*- coding: utf-8 -*-

with open("chapter_17.md", "r", encoding="utf-8") as f:
    text = f.read()

# 1. антоновских яблок
text = text.replace("ароматом антоновских яблок", "ароматом храмовых яблок")

# 2. пять лет -> два года
text = text.replace("Запечатанное пять лет назад тело", "Запечатанное два года назад тело")
text = text.replace("Воспоминания, запертые на пять лет", "Воспоминания, запертые на два года")
text = text.replace("я впервые за пять лет почувствовал страх", "я впервые за два года почувствовал страх")

# Strip trailing whitespaces:
lines = [l.rstrip() for l in text.splitlines()]
text = "\n".join(lines) + "\n"

with open("chapter_17.md", "w", encoding="utf-8") as f:
    f.write(text)

print("Updated ch17.")
