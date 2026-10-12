# -*- coding: utf-8 -*-

with open("chapter_10.md", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("Договор Семи Печатей", "Договор Семи Отсечений")
text = text.replace("Закон Семи Печатей", "Закон Семи Отсечений")
text = text.replace("осталось восемьдесят дней. Восемь декад.", "осталось пятьдесят три дня. Чуть больше пяти декад.")
text = text.replace("восемьдесят суток.", "пятьдесят три дня.")

with open("chapter_10.md", "w", encoding="utf-8") as f:
    f.write(text)

print("Updated ch10.")
