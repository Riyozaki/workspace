#!/usr/bin/env python3
"""Применение правок к главе: каждая замена должна встретиться ровно один раз.

    python3 scripts/apply_edits.py <глава.md> <edits.py> [--dry]

edits.py определяет EDITS = [(было, стало, метка), ...].
Если хоть одно «было» встречается не ровно один раз — ничего не записывается.
Правило из additiontoSkill §6: только последовательно, count==1, потом скан
FFFD и «недел».
"""
import sys, re, importlib.util

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    dry = '--dry' in sys.argv
    path, edits_path = args
    spec = importlib.util.spec_from_file_location("edits", edits_path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    t = open(path, encoding='utf-8').read()
    bad = [(tag, t.count(old)) for old, new, tag in mod.EDITS if t.count(old) != 1]
    if bad:
        for tag, c in bad:
            print(f"!! {tag}: count={c}")
        sys.exit(1)
    for old, new, tag in mod.EDITS:
        t = t.replace(old, new)
    if not dry:
        open(path, 'w', encoding='utf-8').write(t)
    print(f"{'DRY ' if dry else ''}OK: {len(mod.EDITS)} правок; FFFD={t.count(chr(0xfffd))} "
          f"недел={len(re.findall('недел', t, re.I))} слов={len(re.findall(r'[А-Яа-яЁё]+', t))}")

if __name__ == '__main__':
    main()
