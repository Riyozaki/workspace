#!/usr/bin/env python3
"""
Генератор SVG «Пеликан на велосипеде».

Геометрия (колёса, спицы) считается кодом, чтобы всё было симметрично и точно.
Перья, клюв, горловой мешок — авторские кривые Безье.

Запуск:
    python3 build_svg.py          -> pelican-on-bicycle.svg (сцена с фоном)
                                     + pelican-on-bicycle.transparent.svg (без фона)
"""

import math
import re
from pathlib import Path

W, H = 1000, 700

# ---------------------------------------------------------------- палитра ----
C = {
    "sky_top": "#dff1fb",
    "sky_bot": "#fffaf0",
    "sun": "#ffd98e",
    "road": "#e8e0d2",
    "road_line": "#d3c8b4",
    "tire": "#2b2f3a",
    "tire_edge": "#1b1e26",
    "rim": "#b9c3cd",
    "spoke": "#98a4b1",
    "hub": "#5c6773",
    "frame": "#1f7a6c",
    "frame_dark": "#14544a",
    "metal": "#6b7480",
    "metal_dark": "#4d5560",
    "saddle": "#5b4634",
    "body": "#fdfbf5",
    "body_shade": "#e9e2d3",
    "body_line": "#d8cfbc",
    "wing": "#cdd8e3",
    "wing_line": "#9fadbb",
    "tail": "#c3ceda",
    "beak": "#f4b23c",
    "beak_dark": "#d9902a",
    "pouch": "#f8cd79",
    "pouch_line": "#e0ab4f",
    "leg": "#f0a83c",
    "leg_dark": "#cf8a2a",
    "eye": "#2b2f3a",
    "fish": "#6fa8c7",
    "fish_dark": "#4d87a8",
    "speed": "#ffffff",
}


def spokes(cx: float, cy: float, r: float, n: int = 16) -> str:
    """Спицы колеса: n линий из центра к ободу."""
    out = []
    for i in range(n):
        a = math.radians(i * 360.0 / n)
        x2 = cx + r * math.cos(a)
        y2 = cy + r * math.sin(a)
        out.append(f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>')
    return "\n      ".join(out)


def wheel(cx: float, cy: float, name: str) -> str:
    return f"""    <!-- {name} -->
    <g id="{name}">
      <circle cx="{cx}" cy="{cy}" r="96" fill="none" stroke="{C['tire']}" stroke-width="17"/>
      <circle cx="{cx}" cy="{cy}" r="104" fill="none" stroke="{C['tire_edge']}" stroke-width="3"/>
      <circle cx="{cx}" cy="{cy}" r="88" fill="none" stroke="{C['tire_edge']}" stroke-width="2"/>
      <circle cx="{cx}" cy="{cy}" r="84" fill="none" stroke="{C['rim']}" stroke-width="6"/>
      <g stroke="{C['spoke']}" stroke-width="3" stroke-linecap="round">
      {spokes(cx, cy, 81)}
      </g>
      <circle cx="{cx}" cy="{cy}" r="14" fill="{C['hub']}"/>
      <circle cx="{cx}" cy="{cy}" r="5" fill="#dfe5ea"/>
    </g>"""


def speed_lines() -> str:
    lines = [(95, 330, 195), (70, 372, 160), (110, 415, 190), (150, 288, 130)]
    out = []
    for x, y, wdt in lines:
        out.append(
            f'<line x1="{x}" y1="{y}" x2="{x + wdt}" y2="{y}" '
            f'stroke="{C["speed"]}" stroke-width="7" stroke-linecap="round" opacity="0.75"/>'
        )
    return "\n      ".join(out)


SCENE_BG = f"""  <g id="scene-bg">
    <rect width="{W}" height="{H}" fill="url(#sky)"/>
    <circle cx="858" cy="118" r="62" fill="{C['sun']}" opacity="0.5"/>
    <circle cx="858" cy="118" r="40" fill="{C['sun']}" opacity="0.8"/>

    <!-- дорога -->
    <rect x="0" y="575" width="{W}" height="125" fill="{C['road']}"/>
    <rect x="0" y="575" width="{W}" height="6" fill="{C['road_line']}"/>
    <g stroke="{C['road_line']}" stroke-width="6" stroke-dasharray="46 34" stroke-linecap="round">
      <line x1="0" y1="655" x2="1000" y2="655"/>
    </g>

    <!-- тень под велосипедом -->
    <ellipse cx="470" cy="586" rx="290" ry="17" fill="#000000" opacity="0.10"/>

    <!-- линии скорости -->
    <g id="speed">
      {speed_lines()}
    </g>
  </g>
"""

DUST = """  <g id="dust" opacity="0.5">
    <circle cx="180" cy="566" r="7" fill="#ffffff"/>
    <circle cx="150" cy="556" r="4.5" fill="#ffffff"/>
    <circle cx="126" cy="568" r="3" fill="#ffffff"/>
  </g>
"""


def build_svg(bare: bool = False) -> str:
    bg = "" if bare else SCENE_BG
    dust = "" if bare else DUST
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}"
     width="{W}" height="{H}" role="img" aria-labelledby="title desc">
  <title id="title">Пеликан на велосипеде</title>
  <desc id="desc">Мультяшный пеликан едет на бирюзовом велосипеде: лапы на педалях,
  крыло лежит на руле, из клюва торчит хвост рыбы. Плоская векторная иллюстрация.</desc>

  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{C['sky_top']}"/>
      <stop offset="1" stop-color="{C['sky_bot']}"/>
    </linearGradient>
    <linearGradient id="frameGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#2a9c89"/>
      <stop offset="1" stop-color="{C['frame_dark']}"/>
    </linearGradient>
    <radialGradient id="bellyShade" cx="0.42" cy="0.3" r="0.85">
      <stop offset="0" stop-color="#ffffff"/>
      <stop offset="1" stop-color="{C['body_shade']}"/>
    </radialGradient>
    <linearGradient id="pouchGrad" x1="0" y1="0" x2="0.5" y2="1">
      <stop offset="0" stop-color="{C['pouch']}"/>
      <stop offset="1" stop-color="#efb455"/>
    </linearGradient>
  </defs>

  <!-- ============================ ФОН ============================ -->
{bg}
  <!-- ========================== КОЛЁСА ========================== -->
{wheel(240, 470, "wheel-rear")}
{wheel(700, 470, "wheel-front")}

  <!-- дальний шатун и педаль -->
  <g id="crank-far" stroke-linecap="round">
    <line x1="450" y1="500" x2="496" y2="452" stroke="{C['metal_dark']}" stroke-width="13"/>
    <rect x="474" y="442" width="46" height="14" rx="7" fill="#39414c"/>
  </g>

  <!-- ====================== ДАЛЬНЯЯ ЛАПА ПЕЛИКАНА ====================== -->
  <g id="leg-far">
    <path d="M 452 332 L 492 436" stroke="{C['leg_dark']}" stroke-width="21"
          stroke-linecap="round" fill="none"/>
    <path d="M 470 432 C 484 424, 512 426, 520 436 C 514 447, 484 449, 470 443 Z"
          fill="{C['leg_dark']}"/>
  </g>

  <!-- ========================== РАМА ========================== -->
  <g id="frame" fill="none" stroke="url(#frameGrad)" stroke-width="15"
     stroke-linecap="round" stroke-linejoin="round">
    <!-- цепные перья и подседельная труба -->
    <path d="M 240 470 L 450 500"/>
    <path d="M 240 470 L 392 348"/>
    <path d="M 392 348 L 450 500"/>
    <!-- нижняя и верхняя трубы -->
    <path d="M 450 500 L 655 285"/>
    <path d="M 392 348 L 648 262"/>
    <!-- вилка -->
    <path d="M 660 290 L 700 470" stroke-width="12"/>
  </g>
  <!-- рулевая колонка -->
  <path d="M 642 250 L 666 300" stroke="{C['frame_dark']}" stroke-width="19"
        stroke-linecap="round" fill="none"/>

  <!-- руль (бараньи рога) -->
  <g id="handlebar" fill="none" stroke="{C['metal_dark']}" stroke-width="12" stroke-linecap="round">
    <path d="M 648 256 L 680 246"/>
    <path d="M 680 246 C 718 236, 738 264, 722 292 C 714 306, 700 308, 690 302"/>
  </g>
  <path d="M 686 244 C 700 240, 712 246, 716 254" fill="none" stroke="#2b2f3a"
        stroke-width="14" stroke-linecap="round"/>

  <!-- трансмиссия -->
  <g id="drivetrain">
    <path d="M 240 456 L 450 466 M 240 484 L 450 534" stroke="{C['metal_dark']}"
          stroke-width="6" fill="none"/>
    <circle cx="240" cy="470" r="18" fill="{C['metal']}"/>
    <circle cx="240" cy="470" r="7" fill="#39414c"/>
    <circle cx="450" cy="500" r="37" fill="none" stroke="{C['metal']}" stroke-width="8"/>
    <circle cx="450" cy="500" r="37" fill="none" stroke="{C['metal_dark']}"
            stroke-width="8" stroke-dasharray="4 8"/>
    <circle cx="450" cy="500" r="13" fill="{C['metal_dark']}"/>
    <circle cx="450" cy="500" r="5" fill="#cfd6dd"/>
  </g>

  <!-- седло (почти скрыто телом птицы) -->
  <g id="saddle">
    <line x1="392" y1="348" x2="397" y2="302" stroke="{C['metal']}" stroke-width="11"
          stroke-linecap="round"/>
    <path d="M 352 300 C 366 285, 416 283, 438 291 C 447 295, 442 307, 424 309
             L 372 311 C 357 311, 347 307, 352 300 Z" fill="{C['saddle']}"/>
  </g>

  <!-- ============================ ПЕЛИКАН ============================ -->
  <!-- хвост -->
  <path id="tail" d="M 345 262 C 306 270, 268 290, 244 314 C 272 317, 296 313, 318 305
           C 292 323, 272 337, 254 348 C 292 352, 326 337, 352 312 Z"
        fill="{C['tail']}" stroke="{C['wing_line']}" stroke-width="3"/>

  <!-- тело -->
  <path id="body" d="M 340 258
          C 372 216, 452 196, 520 214
          C 556 224, 574 250, 566 284
          C 556 320, 508 348, 456 350
          C 414 352, 382 338, 360 316
          C 344 300, 334 278, 340 258 Z"
        fill="url(#bellyShade)" stroke="{C['body_line']}" stroke-width="3"/>

  <!-- голова + шея + клюв (приподняты над рулём) -->
  <g id="head-unit" transform="translate(2,-12)">
    <!-- голова -->
    <g id="head">
      <circle cx="580" cy="150" r="31" fill="{C['body']}" stroke="{C['body_line']}" stroke-width="3"/>
      <!-- хохолок -->
      <path d="M 558 128 C 550 116, 552 106, 560 99 C 564 109, 570 115, 578 120
               C 574 110, 578 102, 586 97 C 588 107, 592 114, 598 119
               C 588 124, 570 127, 558 128 Z"
            fill="{C['wing']}" stroke="{C['wing_line']}" stroke-width="2"/>
      <!-- глаз -->
      <circle cx="590" cy="126" r="8.5" fill="{C['eye']}"/>
      <circle cx="593" cy="123" r="3" fill="#ffffff"/>
    </g>

    <!-- шея (поверх стыка головы, чтобы шов не торчал) -->
    <path id="neck" d="M 546 244 C 574 226, 586 196, 578 162"
          fill="none" stroke="{C['body']}" stroke-width="46" stroke-linecap="round"/>

    <!-- рыба: торчит из клюва (рисуется до клюва, виден только хвост) -->
    <g id="fish">
      <path d="M 706 190 C 722 176, 752 176, 768 190 C 752 204, 722 204, 706 190 Z"
            fill="{C['fish']}"/>
      <path d="M 764 190 L 790 176 L 785 190 L 790 204 Z" fill="{C['fish_dark']}"/>
      <path d="M 736 182 C 742 186, 742 194, 736 198" stroke="{C['fish_dark']}"
            stroke-width="2.5" fill="none" stroke-linecap="round"/>
    </g>

    <!-- клюв и горловой мешок -->
    <g id="beak">
      <!-- горловой мешок -->
      <path d="M 598 170 C 640 186, 690 194, 740 196
               C 736 216, 712 238, 676 242
               C 640 244, 610 212, 598 170 Z"
            fill="url(#pouchGrad)" stroke="{C['pouch_line']}" stroke-width="3"/>
      <path d="M 616 190 C 636 216, 664 230, 696 226" stroke="{C['pouch_line']}"
            stroke-width="3" fill="none" stroke-linecap="round" opacity="0.7"/>
      <!-- верхний клюв -->
      <path d="M 598 138 C 648 144, 700 160, 744 180
               C 752 184, 750 194, 740 196
               C 692 198, 638 182, 600 164
               C 592 159, 590 144, 598 138 Z"
            fill="{C['beak']}" stroke="{C['beak_dark']}" stroke-width="3"/>
      <path d="M 604 156 C 650 170, 700 184, 742 190" stroke="{C['beak_dark']}"
            stroke-width="3" fill="none" stroke-linecap="round" opacity="0.8"/>
      <!-- кончик-крючок -->
      <path d="M 738 179 C 750 183, 754 190, 748 196 C 742 195, 738 191, 736 186 Z"
            fill="{C['beak_dark']}"/>
      <!-- ноздря -->
      <path d="M 620 150 L 640 155" stroke="{C['beak_dark']}" stroke-width="3.5"
            stroke-linecap="round"/>
    </g>
  </g>

  <!-- крыло (лежит на руле) -->
  <g id="wing">
    <path d="M 500 236
             C 540 226, 580 246, 606 274
             C 634 302, 662 314, 686 314
             C 680 328, 660 338, 636 336
             C 644 346, 638 354, 620 354
             C 578 350, 532 332, 506 302
             C 488 282, 484 250, 500 236 Z"
          fill="{C['wing']}" stroke="{C['wing_line']}" stroke-width="3"/>
    <g stroke="{C['wing_line']}" fill="none" stroke-width="3" stroke-linecap="round" opacity="0.75">
      <path d="M 530 258 C 560 274, 590 292, 618 304"/>
      <path d="M 522 282 C 552 298, 582 314, 606 322"/>
      <path d="M 540 306 C 566 320, 588 330, 608 336"/>
    </g>
    <!-- «кисть» на грипсе -->
    <path d="M 668 300 C 686 292, 702 298, 702 310 C 702 322, 686 328, 672 322 Z"
          fill="{C['body']}" stroke="{C['body_line']}" stroke-width="3"/>
  </g>

  <!-- ближняя лапа -->
  <g id="leg-near">
    <path d="M 452 330 C 442 372, 428 418, 414 462 C 408 484, 404 500, 404 514"
          fill="none" stroke="{C['leg']}" stroke-width="22" stroke-linecap="round"/>
    <!-- перепончатая ступня на педали -->
    <path d="M 386 510 C 372 516, 366 528, 372 536 C 380 544, 402 544, 420 538
             C 434 533, 440 522, 434 514 C 424 506, 398 505, 386 510 Z"
          fill="{C['leg']}" stroke="{C['leg_dark']}" stroke-width="3"/>
    <path d="M 380 538 L 384 522 M 398 541 L 398 524 M 416 537 L 412 522"
          stroke="{C['leg_dark']}" stroke-width="2.5" fill="none" stroke-linecap="round"/>
  </g>

  <!-- ближний шатун + педаль (поверх ступни) -->
  <g id="crank-near" stroke-linecap="round">
    <line x1="450" y1="500" x2="404" y2="546" stroke="{C['metal']}" stroke-width="13"/>
    <rect x="380" y="538" width="48" height="15" rx="7" fill="#22262e"/>
    <circle cx="450" cy="500" r="8" fill="#dfe5ea"/>
  </g>

  <!-- пылинка из-под колеса -->
{dust}</svg>
"""


def strip_scene(svg: str) -> str:
    """Убирает фон/пыль из готовой строки (страховка, если bg уже пуст)."""
    svg = re.sub(r'\s*<g id="scene-bg">.*?</g>\s*</g>', "", svg, flags=re.S)
    svg = re.sub(r'\s*<g id="dust"[^>]*>.*?</g>', "", svg, flags=re.S)
    return svg


def main() -> None:
    here = Path(__file__).parent
    scene = build_svg(bare=False)
    bare = build_svg(bare=True)
    for name, content in (
        ("pelican-on-bicycle.svg", scene),
        ("pelican-on-bicycle.transparent.svg", bare),
    ):
        out = here / name
        out.write_text(content, encoding="utf-8")
        print(f"written: {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
