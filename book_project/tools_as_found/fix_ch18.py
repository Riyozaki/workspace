# -*- coding: utf-8 -*-

with open("chapter_18.md", "r", encoding="utf-8") as f:
    text = f.read()

# 1. каррарского мрамора
text = text.replace("каррарского мрамора", "прибрежного мрамора")
text = text.replace("каррарский мрамор", "прибрежный мрамор")

# 2. коринфских колонн
text = text.replace("двенадцать коринфских колонн", "двенадцать монолитных колонн")

# 3. пять лет -> два года
text = text.replace("А я пять лет был трупом.", "А я два года был трупом.")
text = text.replace("скопленная за пять лет молчания", "скопленная за два года молчания")
text = text.replace("Пять лет в глубине его запечатанной души копилась", "Два года в глубине его запечатанной души копилась")
text = text.replace("Пять лет лекарь считал, что спасение — в бесчувствии.", "Два года лекарь считал, что спасение — в бесчувствии.")

# 4. патриарх Гавриил -> первосвященник Гавел
text = text.replace("Старый патриарх Гавриил", "Старый патриарх Гавел")

# Strip trailing whitespaces:
lines = [l.rstrip() for l in text.splitlines()]
text = "\n".join(lines) + "\n"

with open("chapter_18.md", "w", encoding="utf-8") as f:
    f.write(text)

print("Updated ch18.")
