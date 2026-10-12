# -*- coding: utf-8 -*-

# ch1
with open('chapter_1.md', 'r', encoding='utf-8') as f:
    t = f.read()
t = t.replace('Рука его не дрожала перед разверзнутой раной, а сердце оставалось невозмутимо', 'Рука его не ведала дрожи перед разверзнутой раной, сердце же пребывало в покое')
with open('chapter_1.md', 'w', encoding='utf-8') as f:
    f.write(t)

# ch5
with open('chapter_5.md', 'r', encoding='utf-8') as f:
    t = f.read()
t = t.replace('Не от худой воды и не от сырой земли, а от тайных нечистых червей, коих бесы моровой ямы вдыхают в человеков грешных!', 'Рождаются они отнюдь не от худой воды или сырой земли — черви моровой ямы гнездятся в человеках грешных!')
with open('chapter_5.md', 'w', encoding='utf-8') as f:
    f.write(t)

# ch6
with open('chapter_6.md', 'r', encoding='utf-8') as f:
    t = f.read()
t = t.replace('он ощутил этот мороз не как сухую цифру отчета, а как физическую, колющую боль в нервных окончаниях щек', 'он ощутил этот мороз как физическую, острую боль в замерзших нервах щек, отринув привычный расчет')
with open('chapter_6.md', 'w', encoding='utf-8') as f:
    f.write(t)

# ch8
with open('chapter_8.md', 'r', encoding='utf-8') as f:
    t = f.read()
t = t.replace('яростно дернула упряжь', 'резко дернула упряжь')
with open('chapter_8.md', 'w', encoding='utf-8') as f:
    f.write(t)

# ch9
with open('chapter_9.md', 'r', encoding='utf-8') as f:
    t = f.read()
t = t.replace('Барометрическое давление упало с пугающей внезапностью', 'Давление воздуха упало с пугающей внезапностью')
t = t.replace('Молекулы геосмина, рожденные почвенными бактериями в период засухи, поднимались в воздух с первыми каплями', 'Тяжелый запах сырой земли, спавшей под слоем щебня, поднимался в воздух с первыми каплями')
with open('chapter_9.md', 'w', encoding='utf-8') as f:
    f.write(t)

# ch11
with open('chapter_11.md', 'r', encoding='utf-8') as f:
    t = f.read()
t = t.replace('эндолимфа внутреннего уха всколыхнулась живой волной', 'жидкость во внутреннем ухе всколыхнулась живой волной')
with open('chapter_11.md', 'w', encoding='utf-8') as f:
    f.write(t)

# ch12
with open('chapter_12.md', 'r', encoding='utf-8') as f:
    t = f.read()
t = t.replace('в яростную схватку со временем', 'в отчаянную схватку со временем')
with open('chapter_12.md', 'w', encoding='utf-8') as f:
    f.write(t)

# ch14
with open('chapter_14.md', 'r', encoding='utf-8') as f:
    t = f.read()
t = t.replace('Коронная крепость строилась не для защиты от внешнего врага, а ради удержания внутренней торговли в железных тисках столичной монополии.', 'Коронная крепость строилась ради удержания внутренней торговли в железных тисках столичной монополии, отсекая любые мысли о бунте.')
with open('chapter_14.md', 'w', encoding='utf-8') as f:
    f.write(t)

# ch15
with open('chapter_15.md', 'r', encoding='utf-8') as f:
    t = f.read()
t = t.replace('Богемский хрусталь, листовое зеркальное стекло', 'Вергенский хрусталь, листовое зеркальное стекло')
with open('chapter_15.md', 'w', encoding='utf-8') as f:
    f.write(t)

print("All audit fixes applied.")
