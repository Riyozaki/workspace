# -*- coding: utf-8 -*-

with open("chapter_8.md", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("А в груди Лукаса пять лет царило ледяное безмолвие контракта.", "А в груди Лукаса два года царило ледяное безмолвие контракта.")
text = text.replace("По нервным стволам, спавшим пять лет,", "По нервным стволам, спавшим два года,")
text = text.replace("пораженных скверной Бездны", "пораженных скверной Пустоты")

with open("chapter_8.md", "w", encoding="utf-8") as f:
    f.write(text)

print("Updated ch8.")
