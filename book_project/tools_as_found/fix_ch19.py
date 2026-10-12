# -*- coding: utf-8 -*-

with open("chapter_19.md", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Гавриил -> Гавел
text = text.replace("Гавриилом", "Гавелом")
text = text.replace("Гавриил", "Гавел")

# 2. пять лет -> два года
text = text.replace("Пять лет ты нес тяжесть чужого обмана", "Два года ты нес тяжесть чужого обмана")
text = text.replace("Он впервые за пять лет почувствовал", "Он впервые за два года почувствовал")
text = text.replace("которое пять лет назад казалось утраченным навсегда", "которое два года назад казалось утраченным навсегда")

# 3. крестным знамением -> благословил его священным знаком Света
text = text.replace("благословил его крестным знамением", "благословил его священным знаком Света")

# Strip trailing whitespaces:
lines = [l.rstrip() for l in text.splitlines()]
text = "\n".join(lines) + "\n"

with open("chapter_19.md", "w", encoding="utf-8") as f:
    f.write(text)

print("Updated ch19.")
