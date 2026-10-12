import re
import sys

def lint(text):
    errors = []
    warnings = []
    
    # 1. Semicolons
    if ';' in text:
        count = text.count(';')
        errors.append(f"Found {count} semicolons (;). Strict rule: 0 semicolons.")
        
    # 2. "не X, а Y" / "не X, но Y" / etc.
    ne_patterns = [
        r'\bне\s+[\w\-]+,\s+а\b',
        r'\bне\s+[\w\-]+,\s+но\b',
        r'\bне\s+[\w\-]+\s+[\w\-]+,\s+а\b',
        r'Это\s+была\s+не\s+[\w\-]+\.\s+Это\s+был',
        r'Он\s+не\s+[\w\-]+,\s+лишь\b'
    ]
    for pat in ne_patterns:
        m = re.findall(pat, text, flags=re.IGNORECASE)
        if m:
            errors.append(f"Forbidden 'не X, [а] Y' pattern: {m}")

    # 3. Forbidden clichés
    cliches = [
        "гробовая тишина", "гробовой тишине", "повисла пауза", "повисла тишина",
        "сердце пропустило удар", "по спине пробежал холодок", "время остановилось",
        "воздух стал гуще", "что-то внутри оборвалось", "волосы встали дыбом",
        "кровь застыла в жилах", "мурашки побежали", "перехватило дыхание"
    ]
    for c in cliches:
        if c in text.lower():
            errors.append(f"Forbidden cliché: '{c}'")

    # 4. Forbidden empty adjectives
    empty_adj = [
        "невероятный", "невероятная", "невероятное", "невероятные",
        "неописуемый", "неописуемая", "неописуемое",
        "леденящий", "леденящая", "леденящее",
        "оглушительный", "оглушительная", "оглушительное",
        "пронзительный", "пронзительная",
        "зловещий", "зловещая", "зловещее",
        "яростный", "яростная",
        "призрачный", "призрачная",
        "эфемерный", "эфемерная",
        "судьбоносный", "судьбоносная"
    ]
    for adj in empty_adj:
        m = re.findall(r'\b' + adj + r'\b', text, flags=re.IGNORECASE)
        if m:
            errors.append(f"Forbidden empty adjective: '{adj}'")

    # 5. Introductory AI markers & boilerplate
    markers = [
        "в современном мире", "стоит отметить", "важно понимать", "ни для кого не секрет",
        "таким образом", "тем не менее", "подводя итог", "является", "данный", "данная"
    ]
    for mk in markers:
        m = re.findall(r'\b' + mk + r'\b', text, flags=re.IGNORECASE)
        if m:
            errors.append(f"Forbidden bureaucratic / AI marker: '{mk}'")

    # 6. Check words count
    words = re.findall(r'[а-яА-ЯёЁa-zA-Z0-9\-]+', text)
    word_count = len(words)
    print(f"Total word count: {word_count}")

    # 7. Word frequencies (no word > 1 / 400 words, except prepositions/pronouns)
    from collections import Counter
    stop_words = set("""и в не на с что он то как я но они по к у из за о его от ее все ее ей им них
    был была было были же вы мы ли да если уже или даже бы до для же чтобы сам себя только так
    под во перед при через над него нее них им ими нему ней ним ними этот эта это эти этого этой
    этих этому этим этими о об обо пере ко со изо ото надо подо через""".split())
    
    counter = Counter([w.lower() for w in words if len(w) > 3 and w.lower() not in stop_words])
    for w, c in counter.most_common(15):
        ratio = word_count / c
        if ratio < 350:
            warnings.append(f"Frequent word '{w}': count={c}, ratio=1/{int(ratio)} words")

    print("\n--- LINT SUMMARY ---")
    if errors:
        print(f"ERRORS ({len(errors)}):")
        for e in errors:
            print("  [ERROR]", e)
    else:
        print("No strict errors found.")
        
    if warnings:
        print(f"WARNINGS ({len(warnings)}):")
        for w in warnings:
            print("  [WARN]", w)
    else:
        print("No warnings.")
    return len(errors) == 0

if __name__ == '__main__':
    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        lint(f.read())
