#!/usr/bin/env python3
"""
Build every showcase document, validate it, and render QA previews.

    .venv/bin/python showcase/build_all.py            # build + validate
    .venv/bin/python showcase/build_all.py --preview  # also render PNGs
    .venv/bin/python showcase/build_all.py --clean    # remove out/ first

Exit code is non-zero if any generator fails or any validation reports FAIL,
so this is safe to wire into CI.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT = HERE / "out"
PY = sys.executable

# (label, command, produced file)
STEPS = [
    ("charts (matplotlib)", [PY, "showcase/make_charts.py"], None),
    ("whitepaper (docx)", ["node", "showcase/build_whitepaper.js"],
     "Модернизация_сети_накопителей.docx"),
    ("model (xlsx)", [PY, "showcase/build_workbook.py"],
     "Финансовая_модель_накопители.xlsx"),
    ("deck (pptx)", ["node", "showcase/build_deck.js"],
     "Совет_директоров_накопители.pptx"),
    ("one-pager (pdf)", [PY, "showcase/build_onepager.py"],
     "Резюме_программы_одна_страница.pdf"),
]

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"


def run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true", help="render QA PNGs")
    ap.add_argument("--clean", action="store_true", help="wipe out/ first")
    args = ap.parse_args()

    if args.clean and OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    produced: list[Path] = []

    for label, cmd, artefact in STEPS:
        started = time.time()
        code, output = run(cmd)
        elapsed = time.time() - started
        if code != 0:
            print(f"{RED}FAIL{RESET}  {label}  ({elapsed:.1f}s)")
            print(f"{DIM}{output.strip()}{RESET}")
            failures.append(label)
            continue
        print(f"{GREEN}OK{RESET}    {label}  ({elapsed:.1f}s)")
        if artefact:
            produced.append(OUT / artefact)

    print()
    for path in produced:
        if not path.exists():
            print(f"{RED}FAIL{RESET}  missing {path.name}")
            failures.append(path.name)
            continue
        code, output = run([PY, "tools/validate.py", str(path)])
        print(output.rstrip())
        if code != 0:
            failures.append(path.name)

    if args.preview:
        print("rendering previews...")
        for path in produced:
            if not path.exists():
                continue
            target = OUT / f"qa-{path.stem[:18]}"
            code, output = run([PY, "tools/render.py", str(path), "-o", str(target)])
            status = f"{GREEN}OK{RESET}" if code == 0 else f"{RED}FAIL{RESET}"
            print(f"  {status}  {path.name} -> {target.relative_to(REPO)}")
            if code != 0:
                print(f"{DIM}{output.strip()}{RESET}")
                failures.append(f"preview {path.name}")

    print()
    if failures:
        print(f"{RED}{len(failures)} failure(s):{RESET} " + ", ".join(failures))
        return 1
    total = sum(p.stat().st_size for p in produced)
    print(f"{GREEN}all {len(produced)} documents built and validated{RESET} "
          f"({total / 1_000_000:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
