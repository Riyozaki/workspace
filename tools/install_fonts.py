#!/usr/bin/env python3
"""
install_fonts.py — populate assets/fonts/ with document-grade fonts.

The base image ships only DejaVu (6 files). Enough to *render* Cyrillic, but a
document set in DejaVu looks like a terminal. npm already pulls proper families
via @fontsource, so we harvest those.

TWO NON-OBVIOUS THINGS THIS HANDLES:

1. fontconfig cannot read .woff2. Chromium finds system fonts through
   fontconfig, so dropping woff2 files into a directory does nothing — the text
   silently falls back to another family. We convert each one to .ttf.

2. @fontsource ships one file per subset: `inter-latin-400` has no Cyrillic and
   `inter-cyrillic-400` has no Latin, yet both declare the family name "Inter".
   Two files, same family/weight, disjoint coverage — fontconfig picks one and
   the other alphabet degrades to fallback. We merge each family+weight into a
   single TTF covering both alphabets.

Run:  python tools/install_fonts.py
      python tools/install_fonts.py --report
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FONT_OUT = REPO / "assets" / "fonts"
NODE_MODULES = REPO / "node_modules"  # package.json lives at the repo root

# family name -> (npm package, fontsource slug)
FAMILIES = {
    "Inter": ("@fontsource/inter", "inter"),
    "PT Serif": ("@fontsource/pt-serif", "pt-serif"),
    "JetBrains Mono": ("@fontsource/jetbrains-mono", "jetbrains-mono"),
}
WEIGHTS = ["400", "700"]
SUBSETS = ["latin", "cyrillic"]
CYR_TEST = ord("А")
LAT_TEST = ord("A")


def coverage(path: Path) -> tuple[bool, bool]:
    """Return (has_latin, has_cyrillic) for a font file."""
    from fontTools.ttLib import TTFont

    try:
        font = TTFont(str(path), lazy=True, fontNumber=0)
        cmaps = font["cmap"].tables
        return (
            any(LAT_TEST in t.cmap for t in cmaps),
            any(CYR_TEST in t.cmap for t in cmaps),
        )
    except Exception:
        return (False, False)


def merge_subsets(sources: list[Path], dest: Path, family: str) -> bool:
    """
    Merge per-subset woff2 files into one TTF covering every glyph.

    fontTools' merger needs decompressed inputs, so we convert each woff2 to a
    temporary TTF first (setting .flavor = None is the documented way to strip
    woff2 compression).
    """
    from fontTools.merge import Merger
    from fontTools.ttLib import TTFont

    tmp_dir = dest.parent / ".tmp-merge"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_files: list[str] = []
    try:
        for i, src in enumerate(sources):
            font = TTFont(str(src))
            font.flavor = None  # woff2 -> plain sfnt
            out = tmp_dir / f"{dest.stem}-{i}.ttf"
            font.save(str(out))
            tmp_files.append(str(out))

        if len(tmp_files) == 1:
            shutil.copy2(tmp_files[0], dest)
        else:
            merged = Merger().merge(tmp_files)
            merged.save(str(dest))

        has_lat, has_cyr = coverage(dest)
        if not (has_lat and has_cyr):
            print(
                f"  ! {family}: merged file missing "
                f"{'latin' if not has_lat else 'cyrillic'}",
                file=sys.stderr,
            )
        return True
    except Exception as exc:  # noqa: BLE001 - report and continue with others
        print(f"  ! {family} {dest.name}: {exc}", file=sys.stderr)
        return False
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def build_fonts() -> int:
    made = 0
    for family, (pkg, slug) in FAMILIES.items():
        files_dir = NODE_MODULES / pkg / "files"
        if not files_dir.is_dir():
            print(f"  ! {pkg} not installed, skipping {family}", file=sys.stderr)
            continue

        for weight in WEIGHTS:
            sources = [
                files_dir / f"{slug}-{sub}-{weight}-normal.woff2" for sub in SUBSETS
            ]
            sources = [s for s in sources if s.is_file()]
            if not sources:
                continue
            dest = FONT_OUT / f"{slug}-{weight}.ttf"
            if dest.exists():
                made += 1
                continue
            if merge_subsets(sources, dest, family):
                made += 1
    return made


def sync_dejavu() -> int:
    """Copy system DejaVu TTFs — matplotlib and typst want real files on disk."""
    system = Path("/usr/share/fonts/truetype/dejavu")
    if not system.is_dir():
        return 0
    count = 0
    for ttf in system.glob("*.ttf"):
        dst = FONT_OUT / ttf.name
        if not dst.exists():
            shutil.copy2(ttf, dst)
        count += 1
    return count


def report() -> int:
    files = sorted(FONT_OUT.glob("*.ttf"))
    if not files:
        print("no fonts installed — run: python tools/install_fonts.py")
        return 1
    from fontTools.ttLib import TTFont

    print(f"{'file':<32} {'family':<20} latin cyrillic")
    print("-" * 68)
    for f in files:
        has_lat, has_cyr = coverage(f)
        try:
            name = TTFont(str(f), lazy=True)["name"].getDebugName(1) or "?"
        except Exception:
            name = "?"
        print(f"{f.name:<32} {name:<20} {'yes' if has_lat else 'NO ':<5} {'yes' if has_cyr else 'NO'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", action="store_true", help="list fonts and coverage")
    args = ap.parse_args()

    FONT_OUT.mkdir(parents=True, exist_ok=True)
    if args.report:
        return report()

    made = build_fonts()
    dejavu = sync_dejavu()
    expected = len(FAMILIES) * len(WEIGHTS)

    (FONT_OUT / "README.md").write_text(
        "# Fonts\n\n"
        "Generated by `tools/install_fonts.py` — do not hand-edit.\n\n"
        "| File | Role |\n|---|---|\n"
        "| `inter-400.ttf`, `inter-700.ttf` | UI/sans body text |\n"
        "| `pt-serif-400.ttf`, `pt-serif-700.ttf` | serif body text |\n"
        "| `jetbrains-mono-400.ttf`, `jetbrains-mono-700.ttf` | code |\n"
        "| `DejaVu*.ttf` | system fallback, used by matplotlib |\n\n"
        "Each generated TTF merges the @fontsource `latin` and `cyrillic` "
        "subsets into one file, because two files sharing a family name with "
        "disjoint coverage make fontconfig pick one and silently drop the other "
        "alphabet. They are TTF rather than the original woff2 because "
        "fontconfig — and therefore Chromium's system font lookup — cannot read "
        "woff2.\n\n"
        "Licences: Inter, JetBrains Mono, PT Serif are SIL OFL; DejaVu is under "
        "the Bitstream Vera licence.\n",
        encoding="utf-8",
    )
    print(f"  fonts: {made} merged TTF from @fontsource, {dejavu} DejaVu TTF")
    if made < expected:
        # Silently shipping DejaVu-only would mean every document quietly
        # renders in the fallback face, so make this a hard failure.
        print(
            f"  ! expected {expected} generated fonts, got {made} — "
            "run `npm install` first",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
