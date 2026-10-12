# -*- coding: utf-8 -*-

# Fix Chapter 1:
with open("chapter_1.md", "r", encoding="utf-8") as f:
    t1 = f.read()

# [БАГ] Гл. 1, строка 136 — задвоение предложения:
# «Утром в конце сеченя он нашел девушку на циновке. Утром в конце сеченя он нашел девушку на циновке у окна без дыхания.»
dup_target = "Утром в конце сеченя он нашел девушку на циновке. Утром в конце сеченя он нашел девушку на циновке у окна без дыхания."
dup_fix = "Утром в конце сеченя он нашел девушку на циновке у окна без дыхания."

if dup_target in t1:
    t1 = t1.replace(dup_target, dup_fix, 1)
    print("Fixed dup in ch1")
else:
    print("Dup target not found in ch1 directly, checking variants...")
    import re
    t1 = re.sub(r'Утром в конце сеченя он нашел девушку на циновке\.\s*Утром в конце сеченя он нашел девушку на циновке у окна без дыхания\.', dup_fix, t1)

with open("chapter_1.md", "w", encoding="utf-8") as f:
    f.write(t1)

# Fix Chapter 6:
# «десять лет / пять лет» онемения -> «два года»
with open("chapter_6.md", "r", encoding="utf-8") as f:
    t6 = f.read()

# Replace any 5-year numbness with 2 years
# Let's inspect occurrences of "лет" in chapter 6
import re
for m in re.finditer(r'\b(?:пять|десять)\s+лет\b', t6):
    print("ch6:", m.group(0))

# Fix Chapter 7:
with open("chapter_7.md", "r", encoding="utf-8") as f:
    t7 = f.read()

# Check 'яростн', 'Бездна' / 'Пустота'
print("ch7 яростн:", len(re.findall(r'\bяростн\w*\b', t7)))
print("ch7 Бездна:", len(re.findall(r'\bБездна\b', t7)))

