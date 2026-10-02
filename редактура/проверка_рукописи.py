#!/usr/bin/env python3
"""Поабзацная сверка DOCX/Markdown и техническая проверка последнего блока.

Запуск из любой папки: python3 редактура/проверка_рукописи.py
Литературные оценки (естественность диалога, мотивы, достоверность толкования)
этот скрипт не подменяет. Он проверяет воспроизводимые ограничения.
"""
from pathlib import Path
import json
import re
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DOCX = ROOT / 'Хроники_Этериума_Осколки_Бездны_редакция.docx'
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
LAST_EDITED = 38
LAST_BLOCK = range(1, 39)
SHADOW = {
    6: [3093, 3095, 3099, 3192, 3195, 3201, 3210, 3219, 3233, 3265, 3267,
        3269, 3271, 3291, 3311, 3314, 3317, 3325, 3331, 3333, 3335, 3339,
        3342, 3345, 3348, 3350, 3353, 3357, 3362, 3364, 3368, 3370, 3373,
        3375, 3378, 3380, 3382, 3384, 3432, 3434, 3505, 3608, 3610, 3613,
        3615, 3619],
    7: [3723, 3726, 3729, 4087, 4090, 4092, 4094, 4096, 4099, 4102, 4104,
        4106, 4108, 4112, 4125, 4129, 4131, 4135, 4211, 4214, 4216, 4219,
        4221, 4226, 4228, 4232, 4234, 4236, 4238, 4238, 4240, 4244, 4246,
        4248, 4252, 4254, 4256, 4260],
    8: [4404, 4524, 4527, 4529, 4532, 4535, 4537, 4540, 4543, 4547, 4550,
        4552, 4554, 4556, 4559, 4562, 4566, 4569, 4571, 4575, 4577, 4579,
        4582, 4584, 4586, 4590, 4593, 4596, 4598, 4593, 4601, 4603, 4606, 4610,
        4621, 4625, 4627, 4632, 4635, 4639, 4641, 4680, 4686, 4688, 4690,
        4771, 4773, 4805, 4825, 4827, 4829, 4832, 4835],
    21: [11363, 11688, 11691, 11693, 11696, 11724],
    22: [11902, 11904, 11945, 12110, 12112, 12373],
    23: [12397, 12399, 12401, 12700, 12835, 12837, 12866, 12887, 12889],
    24: [12901, 12921, 12923, 12926, 13048, 13184, 13222, 13224,
         13411, 13413, 13474],
    25: [13489, 13491, 13666, 13668, 13671, 13691, 13785, 13788,
         13791, 13793, 13834, 13836, 13859, 13861, 13863, 13865,
         13869, 13874, 13876],
    26: [13981, 13983, 14019, 14182, 14184],
    27: [14595],
    28: [14884, 14886, 14888, 14894, 14918, 14920, 14939, 14941, 14944,
         14946, 14948, 14951, 15028, 15030, 15035, 15037, 15039, 15042,
         15048, 15144, 15247, 15299, 15301, 15304, 15306],
    29: [15367, 15369, 15489, 15491, 15496, 15498, 15500, 15503, 15506,
         15509, 15511, 15513, 15608, 15610, 15634, 15682, 15684],
    30: [15761, 15763, 15788, 15790, 15838, 15840, 15843, 15846, 15874,
         15908, 15912, 15915, 15917, 15919, 15939, 15941, 15990, 15992,
         15994, 16028, 16069, 16071, 16072, 16073, 16075, 16129, 16193,
         16195, 16197, 16199, 16202, 16204, 16208, 16210, 16212],
    31: [16409, 16489, 16491, 16493, 16495, 16497, 16531, 16610, 16702,
         16704, 16706],
    32: [16910, 16947, 16968, 16970, 16973, 16975, 16978, 17023, 17025,
         17027, 17029, 17083, 17085, 17087, 17100, 17121, 17168],
    33: [17265, 17269, 17336, 17376, 17379, 17381, 17384, 17607, 17610,
         17612],
    34: [17940, 17985, 17987, 17989, 17992, 17995],
    35: [18326, 18378, 18381, 18384],
    36: [18635, 18638, 18640, 18642, 18644, 18646, 18878, 18880, 18947,
         18949, 18959, 18961, 18969, 19149, 19151, 19153],
    37: [19249, 19268, 19308, 19345, 19347, 19391, 19412, 19414, 19491,
         19524, 19574, 19685, 19745, 19759, 19802, 19848],
    38: [19878, 19886, 19930, 19954, 20017, 20019, 20022, 20024, 20065,
         20100, 20102, 20112, 20117, 20119, 20122, 20124, 20126, 20129,
         20138, 20140, 20142, 20148, 20155, 20166, 20168, 20170, 20173,
         20176, 20178, 20181, 20183, 20190, 20192, 20203, 20225, 20250,
         20261, 20328, 20344],
}
FORBIDDEN = re.compile(
    r'\b(?:эфирн\w*|сантиметр\w*|секунд\w*|покамест|дозвол\w*|'
    r'ретиров\w*|ежели|поутру|воссед\w*|осведом\w*|ведаю|неведомо|радёшенек)\b', re.I)
SUBST_CH5 = re.compile(r'\b(?:Плечист\w*|Узколиц\w*|Коренаст\w*)\b')
COUNTER_FORMULA = re.compile(r'\bне\b[^.!?…\n]*[,—–]\s*а\b', re.I)
PART_START = re.compile(
    r'^(?:[А-ЯЁ][а-яё]+(?:вшись|ившись|вши|ши)\b|'
    r'(?:Закрыв|Открыв|Прикрыв|Разжав|Сжав|Подняв|Опустив|Убрав|'
    r'Удерживая|Держа|Глядя|Лёжа|Лежа|Сидя|Стоя|Перехватив|'
    r'Прочитав|Повернув|Показав|Передав)\b)')


def indexed_source(chapter):
    result = {}
    for line in (ROOT / 'chapters' / f'ch_{chapter:02d}.txt').read_text().splitlines():
        match = re.match(r'^\[(\d+)\]\s*(.*)$', line)
        if match:
            result[int(match[1])] = match[2]
    return result


def verify():
    with zipfile.ZipFile(DOCX) as package:
        assert package.testzip() is None, 'Повреждён ZIP-контейнер DOCX'
        document = package.read('word/document.xml')
    root = ET.fromstring(document)
    paragraphs = [
        ''.join(t.text or '' for t in p.findall('.//w:t', NS))
        for p in root.findall('w:body/w:p', NS)
    ]
    assert len(paragraphs) == 20363, 'Изменилось число индексированных абзацев'
    starts = [
        (i, int(match[1])) for i, p in enumerate(paragraphs)
        if i >= 50 and (match := re.fullmatch(r'ГЛАВА (\d+)', p))
    ]
    assert [n for _, n in starts] == list(range(1, 39))
    ranges = {}
    for k, (a, n) in enumerate(starts):
        b = starts[k + 1][0] - 1 if k + 1 < len(starts) else len(paragraphs) - 1
        ranges[n] = (a, b)
        if n <= LAST_EDITED:
            md = (ROOT / f'Глава_{n:02d}_редакция.md').read_text().strip()
            md_paragraphs = re.split(r'\n\s*\n', md)
            md_paragraphs[0] = md_paragraphs[0].removeprefix('# ').strip()
            assert md_paragraphs == paragraphs[a:b + 1], f'DOCX/MD: глава {n}'
        else:
            original = indexed_source(n)
            assert all(paragraphs[i] == p for i, p in original.items()), (
                f'Затронута ещё не редактировавшаяся глава {n}')

    report = []
    for n in LAST_BLOCK:
        a, b = ranges[n]
        body = [(i, paragraphs[i]) for i in range(a + 1, b + 1)
                if paragraphs[i] != '· · ·']
        original = indexed_source(n)
        old_body = [p for i, p in original.items() if i > a and p != '· · ·']
        words = sum(len(p.split()) for _, p in body)
        old_words = sum(len(p.split()) for p in old_body)
        sentences = sum(len(re.findall(r'[.!?…]+', p)) for _, p in body)
        ya_starts = sum(p.startswith('Я ') for _, p in body)
        ya_pairs = [(i - 1, i) for i, p in body
                    if p.startswith('Я ') and paragraphs[i - 1].startswith('Я ')]
        assert not ya_pairs, (n, 'Повторные зачины Я', ya_pairs)
        assert 0.04 <= ya_starts / len(body) <= 0.08, (n, 'Доля зачинов Я')
        for i, p in body:
            assert ';' not in p, (i, 'Точка с запятой')
            assert not FORBIDDEN.search(p), (i, 'Запрещённая лексика')
            assert not COUNTER_FORMULA.search(p), (i, 'Шаблон не X, а Y')
            assert not PART_START.match(p), (i, 'Шаблонный деепричастный зачин')
            if n == 5:
                assert not SUBST_CH5.search(p), (i, 'Субстантивированное прилагательное')
            for sentence in re.split(r'(?<=[.!?…])\s+', p):
                assert len(sentence.split()) <= 28, (i, 'Предложение длиннее 28 слов')
                assert len(re.findall(r'\bи\b', sentence.lower())) < 2, (
                    i, 'Повтор союза и в предложении')
        for i in SHADOW.get(n, []):
            assert paragraphs[i].startswith('«') and '»' in paragraphs[i], (
                i, 'Не оформлена реплика Тени')
        report.append({
            'глава': n, 'диапазон': [a, b], 'индексированных_абзацев': b - a + 1,
            'абзацев_без_заголовка_и_разделителей': len(body),
            'слов_исходник': old_words, 'слов_редакция': words,
            'изменение_процентов': round((words / old_words - 1) * 100, 2),
            'среднее_слов_на_предложение': round(words / sentences, 2),
            'зачины_Я_процентов': round(100 * ya_starts / len(body), 2),
            'поабзацная_синхронизация': '100%',
        })
    p_elems = root.findall('w:body/w:p', NS)
    bms = [b.attrib.get(f'{{{NS["w"]}}}name') for b in root.findall('.//w:bookmarkStart', NS)]
    assert bms == [f'chapter{k}' for k in range(1, 39)], ('Нарушены закладки оглавления', bms)
    for idx in range(50, len(p_elems)):
        assert not any(rpr.find('w:i', NS) is not None for rpr in p_elems[idx].findall('.//w:rPr', NS)), (
            idx, 'Остался курсив в тексте главы')
        assert all(r.find('w:rPr', NS) is not None for r in p_elems[idx].findall('w:r', NS)), (
            idx, 'Пропущен w:rPr в прогоне текста')
        assert not re.search(r'[а-яёА-ЯЁ]\s+—\s+(?:мысленно\s+)?(?:подумала|спросила|ответила|призналась|добавила|прошептала)\s+я\b', paragraphs[idx]), (
            idx, 'Неоформленная прямая мысль без кавычек и запятой')
        assert not (paragraphs[idx].endswith('.»') and idx not in (701, 13848)), (
            idx, 'Точка внутри закрывающей кавычки в конце абзаца')
        assert not re.search(r'[,.!?:][А-ЯЁа-яёA-Za-z]', paragraphs[idx]), (
            idx, 'Пропущен пробел после знака препинания')
    # Earlier continuity repairs and the financial anchor at the end of the block.
    assert paragraphs[159] == 'Норд остановил молоток над тросом.'
    assert 'из моих восемнадцати' in paragraphs[7307]
    assert 'шестнадцать серебряных монет' in paragraphs[13828]
    assert 'пяти' in paragraphs[13829] and 'Эфир' in paragraphs[13829]
    assert 'Она не просила' in paragraphs[19998]
    assert 'ровно тридцать восемь с того утра у ямы' in paragraphs[20212]
    assert 'Способностей Мизу у меня нет.' in paragraphs[20338]
    print('DOCX цел. Все 38 отредактированных глав синхронизированы с Markdown.')
    print('Индексы всех 20 363 абзацев сохранены.')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == '__main__':
    verify()
