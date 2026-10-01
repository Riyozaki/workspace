#!/usr/bin/env python3
"""
Генератор иллюстрации «Пеликан на велосипеде» (pelican-on-bicycle.svg).

Геометрия считается здесь (спицы, касательные цепи, педали по углу шатуна),
поэтому рисунок легко править числами. Порядок групп = порядок слоёв:
фон → колёса → дальняя лапа → рама → трансмиссия → ближняя лапа → пеликан → педали/ступицы.
"""
import math

W, H = 900, 650
GROUND = 562

# ---------------------------------------------------------------- палитра ----
OUTLINE = "#9fb0c0"
WHITE_B = "#e6edf4"
WING_A = "#f4f8fb"
WING_B = "#d7e2ec"
BEAK_A = "#f7c04a"
BEAK_B = "#ee9c2b"
POUCH_A = "#f9d089"
POUCH_B = "#f2a94a"
FOOT = "#f0a33c"
LEG = "#4a535d"
LEG_MID = "#6d7783"
LEG_FAR = "#39414a"
LEG_FAR_MID = "#5b646e"

FRAME_A = "#ef5a52"
FRAME_B = "#b32a26"
METAL_A = "#d3d9e0"
METAL_B = "#9aa4b0"
TIRE = "#2c323a"
RIM = "#c7ced7"
SPOKE = "#aab4c0"
DARK = "#333a43"

# ----------------------------------------------------------------- колёса ----
REAR = (250.0, 446.0)
FRONT = (656.0, 446.0)
R_TIRE = 104.0
R_RIM = 91.0
R_SPOKE = 87.0
SPOKES = 16

# ------------------------------------------------------- трансмиссия ---------
BB = (452.0, 462.0)
CHAINRING_R = 30.0
COG_R = 13.0
CRANK = 58.0
CRANK_ANG = math.radians(45.0)
PEDAL_NEAR = (BB[0] + CRANK * math.cos(CRANK_ANG), BB[1] + CRANK * math.sin(CRANK_ANG))
PEDAL_FAR = (BB[0] - CRANK * math.cos(CRANK_ANG), BB[1] - CRANK * math.sin(CRANK_ANG))


def wheel(cx, cy):
    spokes = "\n".join(
        f'      <line x1="{cx - R_SPOKE:.1f}" y1="{cy:.1f}" x2="{cx + R_SPOKE:.1f}" y2="{cy:.1f}" '
        f'transform="rotate({i * 360 / SPOKES:.2f} {cx:.1f} {cy:.1f})"/>'
        for i in range(SPOKES // 2)
    )
    vx = cx + (R_RIM - 2) * math.cos(math.radians(-68))
    vy = cy + (R_RIM - 2) * math.sin(math.radians(-68))
    return f"""  <g>
    <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{R_TIRE:.1f}" fill="none" stroke="{TIRE}" stroke-width="17"/>
    <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{R_TIRE - 8.5:.1f}" fill="none" stroke="#454c56" stroke-width="1.6" opacity=".7"/>
    <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{R_RIM:.1f}" fill="none" stroke="{RIM}" stroke-width="6"/>
    <g stroke="{SPOKE}" stroke-width="2.4" stroke-linecap="round">
{spokes}
    </g>
    <line x1="{cx:.1f}" y1="{cy:.1f}" x2="{vx:.1f}" y2="{vy:.1f}" stroke="#6f7a87" stroke-width="3"/>
  </g>"""


def tube(pts, width):
    d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    return (f'    <path d="{d}" stroke="{FRAME_B}" stroke-width="{width + 5}" stroke-linecap="round" fill="none"/>\n'
            f'    <path d="{d}" stroke="url(#frame)" stroke-width="{width}" stroke-linecap="round" fill="none"/>')


def curve(d, width):
    return (f'    <path d="{d}" stroke="{FRAME_B}" stroke-width="{width + 4}" fill="none" stroke-linecap="round"/>\n'
            f'    <path d="{d}" stroke="url(#frame)" stroke-width="{width}" fill="none" stroke-linecap="round"/>')


def chain_path(a, ra, b, rb):
    """Внешние касательные к двум звёздочкам -> замкнутый контур цепи."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    dist = math.hypot(dx, dy)
    theta = math.atan2(dy, dx)
    phi = math.acos((ra - rb) / dist)
    pairs = []
    for s in (-1, 1):
        ang = theta + s * phi
        pairs.append(((a[0] + ra * math.cos(ang), a[1] + ra * math.sin(ang)),
                      (b[0] + rb * math.cos(ang), b[1] + rb * math.sin(ang))))
    top, bot = sorted(pairs, key=lambda pr: pr[0][1])
    a1, b1 = top
    a2, b2 = bot
    return (f"M {a1[0]:.1f} {a1[1]:.1f} L {b1[0]:.1f} {b1[1]:.1f} "
            f"A {rb:.1f} {rb:.1f} 0 1 0 {b2[0]:.1f} {b2[1]:.1f} "
            f"L {a2[0]:.1f} {a2[1]:.1f} "
            f"A {ra:.1f} {ra:.1f} 0 1 0 {a1[0]:.1f} {a1[1]:.1f} Z")


CHAIN = chain_path(BB, CHAINRING_R + 3, REAR, COG_R + 3)

# ------------------------------------------------------------- педали/лапы ---
NEAR_KNEE = (472.0, 368.0)
NEAR_ANKLE = (PEDAL_NEAR[0] - 2, PEDAL_NEAR[1] - 16)
FAR_KNEE = (442.0, 330.0)
FAR_ANKLE = (PEDAL_FAR[0] + 4, PEDAL_FAR[1] - 16)

svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}"
     role="img" aria-labelledby="title desc">
  <title id="title">Пеликан на велосипеде</title>
  <desc id="desc">Белый пеликан с длинным клювом и горловым мешком едет на красном велосипеде:
  перепончатые лапы на педалях, крыло сложено вдоль туловища, позади — линии движения.</desc>

  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#e8f4fc"/>
      <stop offset="0.62" stop-color="#f6fbfe"/>
      <stop offset="1" stop-color="#eef4f8"/>
    </linearGradient>
    <linearGradient id="ground" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#dfe8ef"/>
      <stop offset="1" stop-color="#eef4f8"/>
    </linearGradient>
    <radialGradient id="shadow" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="#7f93a6" stop-opacity="0.45"/>
      <stop offset="0.65" stop-color="#7f93a6" stop-opacity="0.18"/>
      <stop offset="1" stop-color="#7f93a6" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="body" x1="0.2" y1="0" x2="0.7" y2="1">
      <stop offset="0" stop-color="#ffffff"/>
      <stop offset="0.55" stop-color="#f7fafc"/>
      <stop offset="1" stop-color="{WHITE_B}"/>
    </linearGradient>
    <linearGradient id="wing" x1="0.1" y1="0" x2="0.6" y2="1">
      <stop offset="0" stop-color="{WING_A}"/>
      <stop offset="1" stop-color="{WING_B}"/>
    </linearGradient>
    <linearGradient id="beak" x1="0" y1="0" x2="0.2" y2="1">
      <stop offset="0" stop-color="{BEAK_A}"/>
      <stop offset="1" stop-color="{BEAK_B}"/>
    </linearGradient>
    <linearGradient id="pouch" x1="0" y1="0" x2="0.1" y2="1">
      <stop offset="0" stop-color="{POUCH_A}"/>
      <stop offset="1" stop-color="{POUCH_B}"/>
    </linearGradient>
    <linearGradient id="frame" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{FRAME_A}"/>
      <stop offset="1" stop-color="#d8413c"/>
    </linearGradient>
    <linearGradient id="saddle" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#5c4332"/>
      <stop offset="1" stop-color="#3d2b20"/>
    </linearGradient>
  </defs>

  <!-- ============================================================= фон ===== -->
  <g id="background">
    <rect width="{W}" height="{H}" fill="url(#sky)"/>
    <g fill="#ffffff" opacity=".8">
      <ellipse cx="150" cy="118" rx="66" ry="26"/>
      <ellipse cx="200" cy="104" rx="48" ry="24"/>
      <ellipse cx="106" cy="110" rx="40" ry="20"/>
      <ellipse cx="772" cy="288" rx="54" ry="20" opacity=".75"/>
      <ellipse cx="810" cy="276" rx="38" ry="17" opacity=".75"/>
    </g>
    <circle cx="812" cy="88" r="42" fill="#ffe9a8" opacity=".7"/>
    <circle cx="812" cy="88" r="28" fill="#ffdf85" opacity=".85"/>
    <rect y="{GROUND}" width="{W}" height="{H - GROUND}" fill="url(#ground)"/>
    <line x1="0" y1="{GROUND}" x2="{W}" y2="{GROUND}" stroke="#c3d1dc" stroke-width="3"/>
    <g stroke="#c3d1dc" stroke-width="4" stroke-linecap="round" opacity=".55">
      <line x1="70" y1="598" x2="190" y2="598"/>
      <line x1="320" y1="618" x2="470" y2="618"/>
      <line x1="660" y1="600" x2="748" y2="600"/>
    </g>
  </g>

  <!-- ======================================================== движение ===== -->
  <g id="motion" stroke="#a9cde6" stroke-linecap="round" fill="none">
    <path d="M 92 372 h 90" stroke-width="7"/>
    <path d="M 56 412 h 126" stroke-width="7"/>
    <path d="M 104 452 h 76" stroke-width="7"/>
    <path d="M 146 334 h 54" stroke-width="6" opacity=".8"/>
  </g>
  <g id="shadows">
    <ellipse cx="452" cy="{GROUND + 4}" rx="298" ry="21" fill="url(#shadow)"/>
    <ellipse cx="{REAR[0]:.0f}" cy="{GROUND + 3}" rx="94" ry="13" fill="url(#shadow)"/>
    <ellipse cx="{FRONT[0]:.0f}" cy="{GROUND + 3}" rx="94" ry="13" fill="url(#shadow)"/>
  </g>

  <!-- ========================================================== колёса ===== -->
  <g id="wheels">
{wheel(*REAR)}
{wheel(*FRONT)}
  </g>

  <!-- ======================================= дальняя лапа (за рамой) ======== -->
  <g id="leg-far" fill="none" stroke-linecap="round" stroke-linejoin="round">
    <path d="M 396 250 Q 430 290 {FAR_KNEE[0]:.0f} {FAR_KNEE[1]:.0f} Q 428 372 {FAR_ANKLE[0]:.0f} {FAR_ANKLE[1]:.0f}"
          stroke="{LEG_FAR}" stroke-width="14"/>
    <path d="M 396 250 Q 430 290 {FAR_KNEE[0]:.0f} {FAR_KNEE[1]:.0f} Q 428 372 {FAR_ANKLE[0]:.0f} {FAR_ANKLE[1]:.0f}"
          stroke="{LEG_FAR_MID}" stroke-width="9"/>
    <g transform="translate({PEDAL_FAR[0] + 2:.0f} {PEDAL_FAR[1] - 7:.0f}) rotate(-10)">
      <path d="M -15 -2 C -15 -11 -4 -15 5 -14 C 16 -13 26 -8 29 -2 C 30 1 26 3 19 3 L -11 3 C -14 3 -15 1 -15 -2 Z"
            fill="#d98f33" stroke="#a96a22" stroke-width="2"/>
      <g stroke="#b9762a" stroke-width="1.8" stroke-linecap="round">
        <line x1="20" y1="2" x2="24" y2="-6"/><line x1="11" y1="2" x2="13" y2="-9"/><line x1="2" y1="2" x2="2" y2="-10"/>
      </g>
    </g>
  </g>

  <!-- ============================================================ рама ===== -->
  <g id="frame">
{curve(f"M {REAR[0]:.0f} {REAR[1]:.0f} Q 352 468 {BB[0]:.0f} {BB[1]:.0f}", 11)}
{curve(f"M {REAR[0]:.0f} {REAR[1]:.0f} Q 322 366 394 296", 10)}
{curve(f"M 618 306 Q 636 376 {FRONT[0]:.0f} {FRONT[1]:.0f}", 12)}
{tube([(BB[0], BB[1]), (392, 290)], 13)}
{tube([(BB[0], BB[1]), (618, 306)], 14)}
{tube([(392, 290), (600, 264)], 11)}
{curve("M 599 258 L 620 310", 17)}
    <!-- подседельный штырь и седло -->
    <path d="M 392 292 L 392 276" stroke="{METAL_B}" stroke-width="11" stroke-linecap="round"/>
    <path d="M 392 292 L 392 276" stroke="{METAL_A}" stroke-width="6" stroke-linecap="round"/>
    <path d="M 332 274 C 350 263 394 259 418 268 C 428 272 424 282 406 284 L 350 287 C 336 287 326 281 332 274 Z"
          fill="url(#saddle)" stroke="#2c1e16" stroke-width="2.5"/>
    <!-- рулевая колонка и руль -->
    <path d="M 600 260 L 594 226" stroke="{METAL_B}" stroke-width="12" stroke-linecap="round"/>
    <path d="M 600 260 L 594 226" stroke="{METAL_A}" stroke-width="7" stroke-linecap="round"/>
    <path d="M 650 242 C 632 218 598 216 560 240" fill="none" stroke="{DARK}" stroke-width="9" stroke-linecap="round"/>
    <path d="M 560 240 C 566 234 572 229 579 226" fill="none" stroke="#22272e" stroke-width="13" stroke-linecap="round"/>
    <path d="M 650 242 C 645 235 640 230 634 226" fill="none" stroke="#22272e" stroke-width="13" stroke-linecap="round"/>
    <circle cx="606" cy="222" r="7" fill="#f0c33c" stroke="#c79a22" stroke-width="2"/>
  </g>

  <!-- ============================================== трансмиссия, педали ===== -->
  <g id="drivetrain">
    <path d="{CHAIN}" fill="none" stroke="#6c757f" stroke-width="6" stroke-linejoin="round"/>
    <path d="{CHAIN}" fill="none" stroke="#aab3bd" stroke-width="2" stroke-dasharray="5 4"/>
    <circle cx="{REAR[0]:.0f}" cy="{REAR[1]:.0f}" r="{COG_R:.0f}" fill="none" stroke="{METAL_B}" stroke-width="6"/>
    <path d="M {BB[0]:.0f} {BB[1]:.0f} L {PEDAL_FAR[0]:.1f} {PEDAL_FAR[1]:.1f}" stroke="#7d8894" stroke-width="11" stroke-linecap="round"/>
    <g transform="translate({PEDAL_FAR[0]:.1f} {PEDAL_FAR[1]:.1f}) rotate(-10)">
      <rect x="-23" y="-6" width="46" height="12" rx="4" fill="{DARK}" stroke="#22272e" stroke-width="2"/>
      <line x1="-15" y1="-2" x2="15" y2="-2" stroke="#5b646e" stroke-width="2.4"/>
    </g>
    <circle cx="{BB[0]:.0f}" cy="{BB[1]:.0f}" r="{CHAINRING_R:.0f}" fill="none" stroke="{METAL_B}" stroke-width="7"/>
    <circle cx="{BB[0]:.0f}" cy="{BB[1]:.0f}" r="{CHAINRING_R - 8:.0f}" fill="none" stroke="{METAL_A}" stroke-width="3"/>
    <path d="M {BB[0]:.0f} {BB[1]:.0f} L {PEDAL_NEAR[0]:.1f} {PEDAL_NEAR[1]:.1f}" stroke="{METAL_A}" stroke-width="12" stroke-linecap="round"/>
    <path d="M {BB[0]:.0f} {BB[1]:.0f} L {PEDAL_NEAR[0]:.1f} {PEDAL_NEAR[1]:.1f}" stroke="#8e99a5" stroke-width="4" stroke-linecap="round"/>
    <circle cx="{BB[0]:.0f}" cy="{BB[1]:.0f}" r="9" fill="{METAL_A}" stroke="#7d8894" stroke-width="2.5"/>
  </g>

  <!-- ======================================== ближняя лапа (перед рамой) ==== -->
  <g id="leg-near" fill="none" stroke-linecap="round" stroke-linejoin="round">
    <path d="M 400 256 Q 448 302 {NEAR_KNEE[0]:.0f} {NEAR_KNEE[1]:.0f} Q 492 424 {NEAR_ANKLE[0]:.0f} {NEAR_ANKLE[1]:.0f}"
          stroke="{LEG}" stroke-width="16"/>
    <path d="M 400 256 Q 448 302 {NEAR_KNEE[0]:.0f} {NEAR_KNEE[1]:.0f} Q 492 424 {NEAR_ANKLE[0]:.0f} {NEAR_ANKLE[1]:.0f}"
          stroke="{LEG_MID}" stroke-width="10"/>
    <circle cx="{NEAR_KNEE[0]:.0f}" cy="{NEAR_KNEE[1]:.0f}" r="6.5" fill="{LEG_MID}" stroke="none"/>
  </g>

  <!-- ======================================================== пеликан ====== -->
  <g id="pelican">
    <!-- хвост -->
    <path d="M 312 226 C 276 226 242 242 218 266 C 244 254 262 252 278 256
             C 256 262 238 274 228 292 C 256 278 288 268 318 264 Z"
          fill="url(#wing)" stroke="{OUTLINE}" stroke-width="3.4" stroke-linejoin="round"/>
    <g stroke="{OUTLINE}" stroke-width="2.2" fill="none" opacity=".8">
      <path d="M 284 240 C 264 244 246 252 232 262"/>
      <path d="M 288 256 C 270 262 254 270 242 280"/>
    </g>

    <!-- силуэт: туловище + шея + голова одним контуром (без швов) -->
    <path d="M 300 240
      C 300 190 330 148 382 138
      C 412 132 440 140 454 158
      C 464 130 492 104 522 98
      C 530 74 556 62 582 72
      C 604 80 610 98 602 114
      C 598 130 586 140 568 144
      C 536 152 510 174 492 198
      C 482 220 478 246 452 264
      C 420 282 372 282 340 270
      C 318 262 298 256 300 240 Z"
      fill="url(#body)" stroke="{OUTLINE}" stroke-width="3.6" stroke-linejoin="round"/>

    <!-- мягкая тень по низу туловища -->
    <path d="M 336 266 C 372 278 420 276 450 260 C 470 248 478 228 484 210
             C 486 236 476 258 452 272 C 420 288 366 286 336 266 Z"
          fill="#cfdbe6" opacity=".5"/>

    <!-- крыло -->
    <path d="M 442 174 C 472 194 468 234 432 252 C 398 268 348 268 318 250
             C 304 241 308 226 326 222 C 362 212 406 192 442 174 Z"
          fill="url(#wing)" stroke="{OUTLINE}" stroke-width="3.4" stroke-linejoin="round"/>
    <g stroke="{OUTLINE}" stroke-width="2.4" fill="none" opacity=".85">
      <path d="M 352 224 C 380 232 400 244 410 258"/>
      <path d="M 378 212 C 402 222 420 234 430 248"/>
      <path d="M 402 200 C 422 210 438 222 446 236"/>
    </g>
    <path d="M 318 250 C 336 260 360 264 380 260 C 358 268 330 264 318 250 Z" fill="#c3d2df" opacity=".7"/>


    <!-- клюв + горловой мешок -->
    <path d="M 594 100
      C 658 108 718 128 768 148
      C 764 166 740 184 706 196
      C 660 212 608 198 586 164
      C 582 144 585 118 594 100 Z"
      fill="url(#pouch)" stroke="#d3821f" stroke-width="3.2" stroke-linejoin="round"/>
    <path d="M 596 111 C 662 121 718 138 768 150"
          fill="none" stroke="url(#beak)" stroke-width="13" stroke-linecap="round"/>
    <path d="M 596 111 C 662 121 718 138 768 150"
          fill="none" stroke="#d3821f" stroke-width="2.6" stroke-linecap="round"/>
    <path d="M 610 140 C 652 152 696 166 736 176" fill="none" stroke="#e9a445" stroke-width="3" opacity=".75"/>
    <path d="M 604 156 C 638 172 674 184 702 190" fill="none" stroke="#e0913a" stroke-width="2.6" opacity=".6"/>
    <g opacity=".3" transform="translate(652 166) rotate(14)">
      <path d="M -30 0 C -22 -10 -6 -13 6 -8 C 14 -5 20 -2 24 0 C 20 2 14 5 6 8 C -6 13 -22 10 -30 0 Z" fill="#a8611a"/>
      <path d="M 24 0 L 38 -9 C 34 -3 34 3 38 9 Z" fill="#a8611a"/>
      <circle cx="-18" cy="-3" r="2.2" fill="#f9d089"/>
    </g>
    <!-- крючок на кончике клюва -->
    <path d="M 768 148 C 775 157 770 165 760 163 C 766 159 768 153 764 148 Z" fill="#d3821f"/>
    <!-- ноздря -->
    <ellipse cx="618" cy="118" rx="7" ry="3.4" fill="#cf8b2c" opacity=".85" transform="rotate(9 618 118)"/>

    <!-- глаз -->
    <circle cx="578" cy="98" r="11" fill="#fdfefe" stroke="{OUTLINE}" stroke-width="2.2"/>
    <circle cx="580" cy="98" r="6.6" fill="#2c333a"/>
    <circle cx="582.4" cy="95.4" r="2.3" fill="#ffffff"/>
    <ellipse cx="564" cy="122" rx="12" ry="6" fill="#f3b9a0" opacity=".35"/>
  </g>

  <!-- ================================ ближняя педаль и ступицы поверх ======== -->
  <g id="front-most">
    <g transform="translate({PEDAL_NEAR[0]:.1f} {PEDAL_NEAR[1]:.1f}) rotate(6)">
      <rect x="-24" y="-5" width="48" height="13" rx="4" fill="{DARK}" stroke="#22272e" stroke-width="2"/>
      <line x1="-16" y1="-1" x2="16" y2="-1" stroke="#5b646e" stroke-width="2.4"/>
    </g>
    <g transform="translate({PEDAL_NEAR[0] + 2:.0f} {PEDAL_NEAR[1] - 9:.0f}) rotate(6)">
      <path d="M -17 -2 C -17 -12 -5 -17 6 -16 C 18 -15 29 -9 32 -2 C 33 1 29 3 21 3 L -13 3 C -16 3 -17 1 -17 -2 Z"
            fill="{FOOT}" stroke="#c07c26" stroke-width="2.2"/>
      <g stroke="#cf8a2e" stroke-width="2" stroke-linecap="round">
        <line x1="22" y1="2" x2="27" y2="-7"/><line x1="12" y1="2" x2="14" y2="-10"/><line x1="2" y1="2" x2="2" y2="-11"/>
      </g>
    </g>
    <g id="hub-caps">
      <circle cx="{REAR[0]:.0f}" cy="{REAR[1]:.0f}" r="10" fill="{METAL_B}"/>
      <circle cx="{REAR[0]:.0f}" cy="{REAR[1]:.0f}" r="5.5" fill="{METAL_A}"/>
      <circle cx="{FRONT[0]:.0f}" cy="{FRONT[1]:.0f}" r="10" fill="{METAL_B}"/>
      <circle cx="{FRONT[0]:.0f}" cy="{FRONT[1]:.0f}" r="5.5" fill="{METAL_A}"/>
    </g>
  </g>
</svg>
"""

if __name__ == "__main__":
    with open("pelican-on-bicycle.svg", "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"pedal near = ({PEDAL_NEAR[0]:.1f}, {PEDAL_NEAR[1]:.1f}), pedal far = ({PEDAL_FAR[0]:.1f}, {PEDAL_FAR[1]:.1f})")
    print("pelican-on-bicycle.svg written")
