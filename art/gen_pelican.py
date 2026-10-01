#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
"Pelican on a Bike" — flat vector SVG illustration (wheelie).
Geometry is authored in upright space and the whole rider+bike group
is rotated around the rear hub to get the wheelie.
"""
import math
import os

W, H = 960, 720
GROUND = 632
RH = (330, 528)          # rear hub  (pivot of the wheelie)
FH = (730, 528)          # front hub
BB = (520, 546)          # bottom bracket
SEAT = (458, 368)        # seat cluster
HT_TOP = (682, 360)      # head tube top
HT_BOT = (698, 412)      # head tube bottom
BAR = (676, 336)         # handlebar centre
WR = 100                 # wheel radius
TILT = -18               # wheelie angle, degrees

FRAME = "#1f7a8c"
FRAME_D = "#16616f"
FRAME_DD = "#0f4c58"
TIRE = "#2f333b"
TIRE_2 = "#464b56"
LINE = "#b9c9dc"         # outline colour for white plumage
DARK = "#2f333b"

P = []
def add(s): P.append(s)


# ------------------------------------------------------------------ shapes
def feather(bx, by, tx, ty, hw, fill="url(#body2)", stroke=LINE, sw=3):
    """A leaf-shaped feather from (bx,by) to (tx,ty), half width hw."""
    dx, dy = tx - bx, ty - by
    ln = math.hypot(dx, dy) or 1.0
    px, py = -dy / ln * hw, dx / ln * hw
    c1x, c1y = bx + dx * 0.35 + px * 1.15, by + dy * 0.35 + py * 1.15
    c2x, c2y = bx + dx * 0.80 + px * 0.55, by + dy * 0.80 + py * 0.55
    c3x, c3y = bx + dx * 0.80 - px * 0.55, by + dy * 0.80 - py * 0.55
    c4x, c4y = bx + dx * 0.35 - px * 1.15, by + dy * 0.35 - py * 1.15
    return (f'<path d="M{bx:.1f} {by:.1f} C{c1x:.1f} {c1y:.1f} {c2x:.1f} {c2y:.1f} '
            f'{tx:.1f} {ty:.1f} C{c3x:.1f} {c3y:.1f} {c4x:.1f} {c4y:.1f} '
            f'{bx:.1f} {by:.1f} Z" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')


def wing_fan(bx, by, angles, lengths, fill, stroke=LINE, sw=3.5, bulge=0.86):
    """A fan of feathers drawn as a single closed shape with scalloped tips.
    angles: degrees (0 = right, 90 = down). lengths: same order as angles."""
    pts = [(bx + L * math.cos(math.radians(a)), by + L * math.sin(math.radians(a)))
           for a, L in zip(angles, lengths)]
    d = f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"
    for i in range(len(pts) - 1):
        mid = (angles[i] + angles[i + 1]) / 2
        cr = max(lengths[i], lengths[i + 1]) * bulge
        cx, cy = bx + cr * math.cos(math.radians(mid)), by + cr * math.sin(math.radians(mid))
        d += f" Q{cx:.1f} {cy:.1f} {pts[i + 1][0]:.1f} {pts[i + 1][1]:.1f}"
    # inner edge: sweep back to the base
    mid = (angles[0] + angles[-1]) / 2
    cr = min(lengths) * 0.42
    cx, cy = bx + cr * math.cos(math.radians(mid)), by + cr * math.sin(math.radians(mid))
    d += f" Q{cx:.1f} {cy:.1f} {pts[0][0]:.1f} {pts[0][1]:.1f}"
    d += f" Q{bx + (pts[-1][0]-bx)*0.35:.1f} {by + (pts[-1][1]-by)*0.35:.1f} {bx:.1f} {by:.1f} Z"
    return (f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linejoin="round"/>')


def qbez(p0, p1, p2, t):
    u = 1 - t
    return (u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
            u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1])


def bird_wing(base, ctrl, tip, w0, w1, n=3, fill="url(#body)", stroke=LINE,
              sw=3.5, scallop=0.13):
    """Tapered wing: Bezier spine from base to tip, scalloped feather tips."""
    ts = [i / (n * 2) for i in range(n * 2 + 1)][-n:]      # tip region samples
    pts = [qbez(base, ctrl, tip, t) for t in ts]
    # spine direction at the tip
    dx, dy = tip[0] - qbez(base, ctrl, tip, 0.85)[0], tip[1] - qbez(base, ctrl, tip, 0.85)[1]
    ln = math.hypot(dx, dy) or 1
    ux, uy = dx / ln, dy / ln
    nx, ny = -uy, ux
    left, right = [], []
    all_ts = [0, 0.2, 0.4, 0.6, 0.8, 1.0]
    for t in all_ts:
        p = qbez(base, ctrl, tip, t)
        w = (w0 + (w1 - w0) * t) / 2
        left.append((p[0] + nx * w, p[1] + ny * w))
        right.append((p[0] - nx * w, p[1] - ny * w))
    d = f"M{left[0][0]:.1f} {left[0][1]:.1f}"
    for p in left[1:]:
        d += f" L{p[0]:.1f} {p[1]:.1f}"
    # scalloped tip: from the left edge, arcs sweeping to the right edge
    for i in range(n):
        t0, t1 = i / n, (i + 1) / n
        a = (left[-1][0] + (right[-1][0] - left[-1][0]) * t0,
             left[-1][1] + (right[-1][1] - left[-1][1]) * t0)
        b = (left[-1][0] + (right[-1][0] - left[-1][0]) * t1,
             left[-1][1] + (right[-1][1] - left[-1][1]) * t1)
        mx, my = (a[0] + b[0]) / 2 + ux * w1 * scallop, (a[1] + b[1]) / 2 + uy * w1 * scallop
        d += f" Q{mx:.1f} {my:.1f} {b[0]:.1f} {b[1]:.1f}"
    for p in reversed(right[:-1]):
        d += f" L{p[0]:.1f} {p[1]:.1f}"
    d += " Z"
    return (f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linejoin="round"/>')


def catmull(pts, steps=14):
    """Dense smooth points through the given control points."""
    p = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(len(p) - 3):
        p0, p1, p2, p3 = p[i], p[i + 1], p[i + 2], p[i + 3]
        for s in range(steps):
            t = s / steps
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t +
                       (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
                       (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t +
                       (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
                       (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
    out.append(pts[-1])
    return out


def taper(pts, widths, fill="url(#body)", stroke=LINE, sw=3.5):
    """Tube of varying thickness along a smooth spine."""
    spine = catmull(pts)
    n = len(spine)
    left, right = [], []
    for i, (x, y) in enumerate(spine):
        j0, j1 = max(0, i - 1), min(n - 1, i + 1)
        dx, dy = spine[j1][0] - spine[j0][0], spine[j1][1] - spine[j0][1]
        l = math.hypot(dx, dy) or 1
        nx, ny = -dy / l, dx / l
        # interpolate width along the spine
        f = i / (n - 1) * (len(widths) - 1)
        k = min(int(f), len(widths) - 2)
        w = (widths[k] + (widths[k + 1] - widths[k]) * (f - k)) / 2
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
    r0, r1 = widths[0] / 2, widths[-1] / 2
    d = f"M{left[0][0]:.1f} {left[0][1]:.1f}"
    d += "".join(f" L{p[0]:.1f} {p[1]:.1f}" for p in left[1:])
    d += (f" A{r1:.1f} {r1:.1f} 0 0 1 {right[-1][0]:.1f} {right[-1][1]:.1f}")
    d += "".join(f" L{p[0]:.1f} {p[1]:.1f}" for p in reversed(right[:-1]))
    d += (f" A{r0:.1f} {r0:.1f} 0 0 1 {left[0][0]:.1f} {left[0][1]:.1f} Z")
    return (f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round"/>')


def blade(bx, by, ang, ln, hw, fill="url(#body)", stroke=LINE, sw=3.2, curve=0.16):
    """One feather: a tapered blade from (bx,by) toward angle `ang` (deg)."""
    a = math.radians(ang)
    tx, ty = bx + ln * math.cos(a), by + ln * math.sin(a)
    px, py = -math.sin(a), math.cos(a)          # perpendicular
    # slight sweep so it bends like a feather
    cxx, cyy = bx + ln * 0.55 * math.cos(a) - curve * ln * math.sin(a), \
               by + ln * 0.55 * math.sin(a) + curve * ln * math.cos(a)
    r = hw * 0.6                      # rounded tip
    tx2, ty2 = tx - math.cos(a) * r, ty - math.sin(a) * r
    return (f'<path d="M{bx + px * hw:.1f} {by + py * hw:.1f} '
            f'Q{cxx + px * hw * 0.85:.1f} {cyy + py * hw * 0.85:.1f} {tx2:.1f} {ty2:.1f} '
            f'Q{tx + px * r * 0.62:.1f} {ty + py * r * 0.62:.1f} '
            f'{tx - px * r * 0.62:.1f} {ty - py * r * 0.62:.1f} '
            f'Q{cxx - px * hw * 0.85:.1f} {cyy - py * hw * 0.85:.1f} '
            f'{bx - px * hw:.1f} {by - py * hw:.1f} Z" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round"/>')


def feather_set(bx, by, specs, fill="url(#body)", stroke=LINE, sw=3.2):
    """Overlapping blades drawn back-to-front."""
    return "\n  ".join(blade(bx + dx, by + dy, ang, ln, hw, fill, stroke, sw)
                        for dx, dy, ang, ln, hw in specs)


def spokes(cx, cy, r_out=84, r_in=15, n=18, phase=0.1, color="#a7b4c1", w=2.4):
    return "\n      ".join(
        f'<line x1="{cx + r_in * math.cos(phase + i * math.pi / n):.1f}" '
        f'y1="{cy + r_in * math.sin(phase + i * math.pi / n):.1f}" '
        f'x2="{cx + r_out * math.cos(phase + i * math.pi / n):.1f}" '
        f'y2="{cy + r_out * math.sin(phase + i * math.pi / n):.1f}" '
        f'stroke="{color}" stroke-width="{w}" stroke-linecap="round"/>'
        for i in range(n))


def wheel(cx, cy):
    return f'''
  <g>
    <circle cx="{cx}" cy="{cy}" r="{WR}" fill="#f8fbfe"/>
    <circle cx="{cx}" cy="{cy}" r="{WR - 7}" fill="none" stroke="{TIRE}" stroke-width="14"/>
    <circle cx="{cx}" cy="{cy}" r="{WR - 7}" fill="none" stroke="{TIRE_2}" stroke-width="14"
            stroke-dasharray="6 12"/>
    <circle cx="{cx}" cy="{cy}" r="86" fill="none" stroke="#dbe4ed" stroke-width="9"/>
    <circle cx="{cx}" cy="{cy}" r="79" fill="none" stroke="#eef4f9" stroke-width="3"/>
    {spokes(cx, cy)}
    <circle cx="{cx}" cy="{cy}" r="13" fill="#b3c0cd" stroke="{TIRE}" stroke-width="4"/>
    <circle cx="{cx}" cy="{cy}" r="4.5" fill="{TIRE}"/>
  </g>'''


def tube(x1, y1, x2, y2, w, color, cap="round"):
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
            f'stroke-width="{w}" stroke-linecap="{cap}"/>')


def foot(x, y, rot=0, s=1.0, fill="url(#legF)", stroke="#dd8524"):
    """Webbed pelican foot, pivot at the ankle, toes pointing +x."""
    return (f'<g transform="translate({x} {y}) rotate({rot}) scale({s})">'
            f'<path d="M-6 -12 C 2 -20, 20 -22, 32 -14 C 40 -9, 40 2, 32 7 '
            f'C 20 14, 2 12, -6 4 C -12 -1, -12 -7, -6 -12 Z" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="3" stroke-linejoin="round"/>'
            f'<g stroke="{stroke}" stroke-width="2.4" fill="none" opacity="0.8">'
            f'<path d="M8 -12 C 14 -4, 16 2, 14 8"/><path d="M22 -10 C 27 -3, 28 3, 26 8"/>'
            f'</g></g>')


def band(d, w, fill="url(#body)", stroke=LINE, sw=4):
    """Thick stroked path drawn as an outlined tube."""
    return (f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{w + sw * 2}" '
            f'stroke-linecap="round"/>'
            f'<path d="{d}" fill="none" stroke="{fill}" stroke-width="{w}" stroke-linecap="round"/>')


# ================================================================== DEFS
add(f'''<defs>
  <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#9fd8ff"/>
    <stop offset="0.55" stop-color="#dcf0ff"/>
    <stop offset="1" stop-color="#fdfeff"/>
  </linearGradient>
  <linearGradient id="grass" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#9ed88f"/>
    <stop offset="1" stop-color="#74c168"/>
  </linearGradient>
  <linearGradient id="hillL" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#c3e6d0"/>
    <stop offset="1" stop-color="#a2d5b6"/>
  </linearGradient>
  <linearGradient id="bill" x1="0" y1="0" x2="0.15" y2="1">
    <stop offset="0" stop-color="#ffd27e"/>
    <stop offset="1" stop-color="#f9a12c"/>
  </linearGradient>
  <linearGradient id="pouch" x1="0.1" y1="0" x2="0.5" y2="1">
    <stop offset="0" stop-color="#ffd88f"/>
    <stop offset="1" stop-color="#ef8f1b"/>
  </linearGradient>
  <linearGradient id="body" x1="0.25" y1="0" x2="0.8" y2="1">
    <stop offset="0" stop-color="#ffffff"/>
    <stop offset="1" stop-color="#d6e4f2"/>
  </linearGradient>
  <linearGradient id="wingB" x1="0" y1="1" x2="0.5" y2="0">
    <stop offset="0" stop-color="#b9cee2"/>
    <stop offset="1" stop-color="#dfeaf6"/>
  </linearGradient>
  <linearGradient id="tailF" x1="0" y1="1" x2="0.4" y2="0">
    <stop offset="0" stop-color="#b2c7dc"/>
    <stop offset="1" stop-color="#d6e3f0"/>
  </linearGradient>
  <linearGradient id="legF" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#ffb264"/>
    <stop offset="1" stop-color="#ed8a2f"/>
  </linearGradient>
  <linearGradient id="legB" x1="0" y1="0" x2="0.3" y2="1">
    <stop offset="0" stop-color="#e79240"/>
    <stop offset="1" stop-color="#cd6d1c"/>
  </linearGradient>
  <radialGradient id="sunG" cx="0.5" cy="0.5" r="0.5">
    <stop offset="0" stop-color="#fff6cf"/>
    <stop offset="0.72" stop-color="#ffe382"/>
    <stop offset="1" stop-color="#ffd75e"/>
  </radialGradient>
  <radialGradient id="sunHalo" cx="0.5" cy="0.5" r="0.5">
    <stop offset="0.55" stop-color="#ffe89a" stop-opacity="0.55"/>
    <stop offset="1" stop-color="#ffe89a" stop-opacity="0"/>
  </radialGradient>
</defs>

<rect width="{W}" height="{H}" fill="url(#sky)"/>
<circle cx="152" cy="126" r="120" fill="url(#sunHalo)"/>
<circle cx="152" cy="126" r="64" fill="url(#sunG)"/>

<g fill="#ffffff">
  <g opacity="0.96">
    <ellipse cx="304" cy="122" rx="58" ry="29"/>
    <ellipse cx="352" cy="108" rx="42" ry="33"/>
    <ellipse cx="258" cy="114" rx="34" ry="23"/>
  </g>
  <g opacity="0.9">
    <ellipse cx="702" cy="84" rx="50" ry="24"/>
    <ellipse cx="744" cy="76" rx="33" ry="26"/>
  </g>
  <g opacity="0.8">
    <ellipse cx="856" cy="206" rx="58" ry="22"/>
    <ellipse cx="812" cy="202" rx="32" ry="18"/>
  </g>
</g>

<path d="M0 566 C 90 476, 214 474, 302 558 C 360 612, 432 612, 472 566
         C 562 476, 702 476, 802 562 C 862 612, 932 612, 960 572 L960 720 L0 720 Z"
      fill="url(#hillL)" opacity="0.92"/>
<rect x="0" y="{GROUND - 4}" width="{W}" height="{H - GROUND + 4}" fill="url(#grass)"/>
<path d="M0 {GROUND - 4} H{W}" stroke="#8ed081" stroke-width="6"/>''')

add(f'''<ellipse cx="{RH[0] + 16}" cy="{GROUND + 18}" rx="132" ry="20" fill="#4a8a52" opacity="0.26"/>
<ellipse cx="{RH[0] + 16}" cy="{GROUND + 16}" rx="94" ry="11" fill="#3d7a46" opacity="0.24"/>
<g stroke="#8fb4d6" stroke-width="3.4" fill="none" stroke-linecap="round" opacity="0.65">
  <path d="M812 128 C 822 118, 830 118, 840 128"/>
  <path d="M840 128 C 850 118, 858 118, 868 128"/>
  <path d="M744 188 C 752 180, 758 180, 766 188"/>
  <path d="M766 188 C 774 180, 780 180, 788 188"/>
</g>
<g stroke="#ffffff" stroke-width="9" stroke-linecap="round" fill="none" opacity="0.85">
  <path d="M118 468 C 188 450, 248 450, 298 460"/>
  <path d="M148 528 C 218 510, 278 510, 318 518"/>
  <path d="M106 394 C 168 378, 218 378, 260 386"/>
</g>''')

# ================================================================== FAR LEG
add(f'''<g>
  {band("M492 300 C 508 326, 520 356, 526 388", 30, "url(#legB)", "#c96a1a", 3)}
  {band("M526 388 C 516 434, 502 500, 496 552", 18, "url(#legB)", "#c96a1a", 3)}
  {foot(496, 560, 4, 1.05, "url(#legB)", "#b85f14")}
</g>''')

# ================================================================== BIKE
bike = [f'<g>{wheel(*RH)}{wheel(*FH)}</g>']
bike.append(f'''<g stroke-linecap="round">
  {tube(RH[0], RH[1], BB[0], BB[1], 13, FRAME_D)}
  {tube(RH[0], RH[1], SEAT[0], SEAT[1], 12, FRAME_D)}
  {tube(BB[0], BB[1], SEAT[0], SEAT[1], 17, FRAME)}
  {tube(BB[0], BB[1], HT_BOT[0] + 2, HT_BOT[1] + 2, 18, FRAME)}
  {tube(SEAT[0], SEAT[1] - 6, HT_TOP[0], HT_TOP[1] - 6, 15, FRAME)}
  {tube(HT_TOP[0], HT_TOP[1], HT_BOT[0], HT_BOT[1], 20, FRAME_DD)}
  {tube(HT_BOT[0] + 3, HT_BOT[1] + 4, FH[0], FH[1], 12, FRAME_DD)}
  {tube(SEAT[0], SEAT[1], 438, 328, 10, "#c3ced9")}
</g>
<g fill="none" stroke-linecap="round">
  <circle cx="{BB[0]}" cy="{BB[1]}" r="27" stroke="#8592a0" stroke-width="6"/>
  <circle cx="{BB[0]}" cy="{BB[1]}" r="27" stroke="#a9b6c3" stroke-width="6" stroke-dasharray="4 9"/>
  <circle cx="{BB[0]}" cy="{BB[1]}" r="14" stroke="#5d6773" stroke-width="4"/>
  <circle cx="{RH[0]}" cy="{RH[1]}" r="14" stroke="#a9b6c3" stroke-width="6"/>
  <path d="M{BB[0] - 27} {BB[1] - 2} L{RH[0] - 12} {RH[1] - 11}" stroke="#8592a0" stroke-width="5"/>
  <path d="M{BB[0] - 25} {BB[1] + 14} L{RH[0] - 12} {RH[1] + 11}" stroke="#8592a0" stroke-width="5"/>
</g>''')

# saddle (drawn before the bird: the pelican sits on it)
bike.append('''<path d="M392 334 C 408 320, 456 311, 500 314 C 512 315, 516 321, 508 327
           C 486 343, 436 355, 404 353 C 386 352, 383 343, 392 334 Z"
        fill="#54392a" stroke="#33231a" stroke-width="4" stroke-linejoin="round"/>
<path d="M400 329 C 420 319, 460 312, 496 314" fill="none" stroke="#6f4c37" stroke-width="4"/>''')

# handlebar + bell
bike.append(f'''<g stroke-linecap="round" fill="none">
  {tube(HT_TOP[0] - 2, HT_TOP[1] - 2, BAR[0] - 8, BAR[1] + 6, 12, "#c3ced9")}
  <path d="M{BAR[0] - 16} {BAR[1] - 12} C {BAR[0] + 26} {BAR[1] - 18}, {BAR[0] + 40} {BAR[1] - 2}, {BAR[0] + 16} {BAR[1] + 14}"
        stroke="#3a3f48" stroke-width="14"/>
  <path d="M{BAR[0] - 16} {BAR[1] - 14} C {BAR[0] - 36} {BAR[1] - 12}, {BAR[0] - 40} {BAR[1] + 4}, {BAR[0] - 22} {BAR[1] + 14}"
        stroke="#3a3f48" stroke-width="14"/>
  <path d="M{BAR[0] + 22} {BAR[1] - 12} C {BAR[0] + 36} {BAR[1] - 2}, {BAR[0] + 32} {BAR[1] + 8}, {BAR[0] + 14} {BAR[1] + 16}"
        stroke="#2a2e35" stroke-width="15"/>
</g>
<g>
  <circle cx="{BAR[0] - 34}" cy="{BAR[1] - 2}" r="3.4" fill="#fff2c4"/>
</g>''')

# crank + pedals
bike.append(f'''<g>
  <circle cx="{BB[0]}" cy="{BB[1]}" r="12" fill="#c3ced9" stroke="#3a3f48" stroke-width="4"/>
  {tube(BB[0], BB[1], 549, 520, 9, "#dde5ee")}
  {tube(BB[0], BB[1], 492, 574, 9, "#aab7c4")}
  <rect x="533" y="512" width="34" height="12" rx="4" fill="#3a3f48" transform="rotate(-20 550 518)"/>
  <rect x="476" y="566" width="34" height="12" rx="4" fill="#5b636e" transform="rotate(-20 493 572)"/>
</g>''')

BIKE = "\n".join(bike)

# ================================================================== PELICAN
bird = []

# ---- tail: short feathers pointing back and down
bird.append(f'''<g>
  {feather_set(474, 320, [
    (6, -14, 186, 138, 22),
    (0, 0, 176, 156, 24),
    (-4, 14, 166, 128, 21),
  ], "url(#tailF)", "#93aec7", 3.2)}
</g>''')

# ---- far wing: single crescent swept up and back, twin tips at the end
bird.append(f'''<g>
  <path d="M492 216 C 442 188, 392 156, 344 114
           C 348 168, 378 222, 424 262
           C 448 276, 480 272, 492 252 Z"
        fill="url(#wingB)" stroke="#aabfd6" stroke-width="3.5" stroke-linejoin="round"/>
  <path d="M474 208 C 434 182, 396 154, 360 124" fill="none" stroke="#c6d8e9" stroke-width="4" opacity="0.85"/>
  <path d="M478 238 C 440 220, 402 202, 366 172" fill="none" stroke="#a2b8d0" stroke-width="2.6" opacity="0.7"/>
  <path d="M430 252 C 442 264, 458 272, 476 274" fill="none" stroke="#9db4cd" stroke-width="2.4" opacity="0.6"/>
</g>''')

# ---- contact shadow where the pelican sits on the saddle
bird.append('''<path d="M400 330 C 428 344, 476 346, 504 334 C 494 350, 436 356, 400 330 Z"
      fill="#3c2a1e" opacity="0.35"/>''')

# ---- body
bird.append('''<g>
  <path d="M456 182 C 504 182, 530 216, 530 258 C 530 304, 500 334, 456 334
           C 412 334, 386 304, 386 258 C 386 214, 414 182, 456 182 Z"
        fill="url(#body)" stroke="#bfd0e2" stroke-width="4"/>
  <path d="M462 328 C 420 328, 392 302, 390 264 C 398 298, 426 318, 468 320 Z"
        fill="#cfdcec" opacity="0.85"/>
  <path d="M414 216 C 402 232, 398 254, 402 274 C 392 250, 396 226, 414 216 Z"
        fill="#ffffff" opacity="0.9"/>
</g>''')

# ---- neck + head
bird.append('''<ellipse cx="486" cy="230" rx="48" ry="40" fill="url(#body)"/>''')
bird.append(band("M474 232 C 478 184, 512 156, 566 152", 64, "url(#body)", "#bfd0e2", 3))
bird.append(band("M566 152 C 586 150, 598 156, 602 168", 58, "url(#body)", "#bfd0e2", 3))

# ---- crest
bird.append(f'''<g>
  {feather(576, 142, 528, 104, 11, "#f2f7fc", LINE, 2.6)}
  {feather(586, 136, 550, 88, 11, "#f2f7fc", LINE, 2.6)}
  {feather(596, 132, 580, 84, 10, "#f2f7fc", LINE, 2.6)}
</g>''')

bird.append('''<circle cx="602" cy="170" r="41" fill="#ffffff" stroke="#bfd0e2" stroke-width="4"/>''')

# ---- bill
bird.append('''<g>
  <path d="M634 150 C 686 142, 738 146, 766 156 C 776 160, 776 168, 766 170
           C 726 176, 668 172, 630 164 Z"
        fill="url(#bill)" stroke="#dd8a1c" stroke-width="3.5" stroke-linejoin="round"/>
  <path d="M632 164 C 642 210, 676 244, 716 242 C 752 240, 772 212, 766 170
           C 740 180, 694 178, 652 170 Z"
        fill="url(#pouch)" stroke="#dd8a1c" stroke-width="3.5" stroke-linejoin="round"/>
  <path d="M632 159 C 672 154, 724 156, 766 162" fill="none" stroke="#dd8a1c" stroke-width="3"/>
  <path d="M650 190 C 668 216, 696 230, 724 226" fill="none" stroke="#e9a542" stroke-width="4" opacity="0.85"/>
  <path d="M644 150 C 694 144, 740 150, 768 158" fill="none" stroke="#ffe3ae" stroke-width="4" opacity="0.9"/>
  <path d="M652 196 C 676 220, 704 230, 730 224" fill="none" stroke="#ffe0ab" stroke-width="6" opacity="0.45"/>
  <circle cx="746" cy="154" r="3.4" fill="#8a5a12"/>
</g>''')

# ---- eye
bird.append('''<circle cx="618" cy="152" r="8.4" fill="#2f333b"/>
<circle cx="621" cy="149" r="3" fill="#ffffff"/>''')

# ---- near wing: slim tapered arm out to the grip
bird.append(f'''<g>
  {taper([(474, 266), (530, 262), (588, 278), (632, 308), (652, 328)], [54, 50, 40, 30, 20], "url(#body)", LINE, 3.5)}
  <path d="M514 252 C 564 260, 606 284, 636 314" fill="none" stroke="{LINE}" stroke-width="2.6" opacity="0.45"/>
  <path d="M512 272 C 556 284, 596 308, 626 334" fill="none" stroke="{LINE}" stroke-width="2.6" opacity="0.35"/>
  {feather(640, 330, 604, 360, 11, "url(#body)", LINE, 3)}
  {feather(650, 342, 622, 368, 10, "url(#body)", LINE, 3)}
  <path d="M644 306 C 668 316, 680 330, 676 344 C 672 358, 652 364, 640 354
           C 626 342, 628 318, 644 306 Z"
        fill="#f2f7fc" stroke="#bfd0e2" stroke-width="3.5" stroke-linejoin="round"/>
  <path d="M642 322 C 656 328, 662 338, 658 344" fill="none" stroke="#c9d9e9" stroke-width="3"/>
  <circle cx="698" cy="318" r="9" fill="#3a3f48"/>
  <circle cx="695" cy="314" r="2.6" fill="#8f9aa6"/>
</g>''')

# ---- near leg to the near pedal: thigh, shin, webbed foot
bird.append(f'''<g>
  {band("M488 302 C 512 324, 532 352, 540 384", 30, "url(#legF)", "#dd8524", 3)}
  {band("M540 384 C 546 420, 546 458, 542 494", 20, "url(#legF)", "#dd8524", 3)}
  {foot(544, 502, -24, 1.05, "url(#legF)", "#dd8524")}
</g>''')

PELICAN = "\n".join(bird)

# ================================================================== OUTPUT
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}"
     role="img" aria-labelledby="t d">
<title id="t">Pelican on a Bike</title>
<desc id="d">A white pelican doing a wheelie on a teal bicycle: one wing on the handlebar,
the other thrown out for balance, webbed orange feet on the pedals.</desc>
{chr(10).join(P)}

<g transform="rotate({TILT} {RH[0]} {RH[1]})">
{BIKE}
{PELICAN}
</g>
</svg>
'''
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pelican_bike.svg")
open(OUT, "w").write(svg)
print("bytes:", len(svg))
