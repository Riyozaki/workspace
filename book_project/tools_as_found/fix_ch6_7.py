# -*- coding: utf-8 -*-

with open("chapter_6.md", "r", encoding="utf-8") as f:
    t6 = f.read()

t6 = t6.replace("впервые за пять лет он ощутил этот мороз", "впервые за два года он ощутил этот мороз")

with open("chapter_6.md", "w", encoding="utf-8") as f:
    f.write(t6)

with open("chapter_7.md", "r", encoding="utf-8") as f:
    t7 = f.read()

t7 = t7.replace("Впервые за пять лет могильного покоя", "Впервые за два года могильного покоя")
t7 = t7.replace("подтачивалась снизу яростным течением", "подтачивалась снизу бурным течением")
t7 = t7.replace("яростно растирая огрубевшую кожу", "упорно растирая огрубевшую кожу")

with open("chapter_7.md", "w", encoding="utf-8") as f:
    f.write(t7)

print("Fixed ch6 and ch7")
