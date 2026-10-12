# -*- coding: utf-8 -*-

with open('chapter_5.md', 'r', encoding='utf-8') as f:
    t5 = f.read()
old5 = 'Не от худой воды и не от сырой земли, а от тайных нечистых червей, коих бесы моровой ямы вдыхают в человека спящего!'
new5 = 'Рождаются они вовсе не от худой воды или сырой земли — черви моровой ямы гнездятся в человеке спящем!'
assert old5 in t5
t5 = t5.replace(old5, new5, 1)
with open('chapter_5.md', 'w', encoding='utf-8') as f:
    f.write(t5)

with open('chapter_9.md', 'r', encoding='utf-8') as f:
    t9 = f.read()
old9 = 'Молекулы геосмина, рожденные почвенными бактериями в пересохших расщелинах, поднялись в воздух с миллиардами'
new9 = 'Древний запах пересохшей земли, таившийся в глубоких расщелинах, поднялся в воздух с миллиардами'
assert old9 in t9
t9 = t9.replace(old9, new9, 1)
with open('chapter_9.md', 'w', encoding='utf-8') as f:
    f.write(t9)

print("Applied precision fixes to ch5 and ch9.")
