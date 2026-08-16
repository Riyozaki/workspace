#!/usr/bin/env python3
"""
Charts that OOXML cannot express natively: a waterfall and a tornado.

Native charts (bar/line/pie) belong in the document as real chart parts so they
stay editable — see build_deck.js. These two have no native PowerPoint or Word
form, so matplotlib is the correct tool, and a rasterised image is the correct
output.
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE = Path(__file__).resolve().parent
FONTS = HERE.parent / "assets" / "fonts"
for f in FONTS.glob("*.ttf"):
    font_manager.fontManager.addfont(str(f))

NAVY, TEAL, CORAL, MUTED, RULE = "#1E2761", "#4A6FA5", "#B85042", "#667085", "#E4E9F0"
plt.rcParams.update({
    "font.family": "Inter", "font.size": 10,
    "axes.edgecolor": RULE, "axes.labelcolor": "#1F2933",
    "text.color": "#1F2933", "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False,
})


def waterfall() -> Path:
    """EBITDA bridge — the classic 'why did the number move' chart."""
    # Anchored to the workbook: EBITDA 2025 = 975, EBITDA 2026 = 1168 (see
    # Прогноз P&L!B9). The bridge must reconcile, not merely look plausible.
    labels = ["EBITDA\n2025", "Объём", "Цена", "Себест.", "Опер.\nрасходы", "EBITDA\n2026"]
    deltas = [975, 161, 96, -41, -23, None]
    fig, ax = plt.subplots(figsize=(9, 4.4))

    running = 0.0
    for i, (label, delta) in enumerate(zip(labels, deltas)):
        if delta is None:  # final total bar
            ax.bar(i, running, color=NAVY, width=0.6)
            ax.text(i, running + 12, f"{running:,.0f}".replace(",", " "),
                    ha="center", fontsize=10, fontweight="bold")
            break
        if i == 0:
            ax.bar(i, delta, color=NAVY, width=0.6)
            ax.text(i, delta + 12, f"{delta:,.0f}".replace(",", " "),
                    ha="center", fontsize=10, fontweight="bold")
            running = delta
            continue
        colour = TEAL if delta > 0 else CORAL
        ax.bar(i, delta, bottom=running, color=colour, width=0.6)
        ax.plot([i - 0.7, i - 0.3], [running, running], color=MUTED, lw=0.8, ls=":")
        ax.text(i, running + delta + (12 if delta > 0 else -26),
                f"{delta:+,.0f}".replace(",", " "), ha="center", fontsize=9,
                color=TEAL if delta > 0 else CORAL, fontweight="bold")
        running += delta

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels)
    ax.set_ylabel("млн ₽")
    ax.set_title("Факторное разложение изменения EBITDA", fontsize=13, fontweight="bold",
                 color=NAVY, pad=14, loc="left")
    ax.yaxis.grid(True, color=RULE, lw=0.8)
    ax.set_axisbelow(True)
    ax.set_ylim(0, 1400)
    fig.tight_layout()
    out = HERE / "assets" / "waterfall.png"
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


def tornado() -> Path:
    """Sensitivity of NPV to each assumption, ranked by impact."""
    drivers = ["Темп роста\nвыручки", "Валовая\nмаржа", "Ставка\nдисконт.",
               "Опер.\nрасходы", "Ставка\nналога"]
    low = [-118, -96, -71, -44, -22]
    high = [126, 101, 66, 47, 22]
    order = sorted(range(len(drivers)), key=lambda i: high[i] - low[i])
    drivers = [drivers[i] for i in order]
    low = [low[i] for i in order]
    high = [high[i] for i in order]

    fig, ax = plt.subplots(figsize=(8, 4.2))
    y = range(len(drivers))
    ax.barh(y, low, color=CORAL, height=0.6, label="−10% к допущению")
    ax.barh(y, high, color=TEAL, height=0.6, label="+10% к допущению")
    for i, (lo, hi) in enumerate(zip(low, high)):
        ax.text(lo - 6, i, f"{lo}", va="center", ha="right", fontsize=9, color=CORAL)
        ax.text(hi + 6, i, f"+{hi}", va="center", ha="left", fontsize=9, color=TEAL)

    ax.axvline(0, color="#1F2933", lw=1.2)
    ax.set_yticks(list(y))
    ax.set_yticklabels(drivers)
    ax.set_xlabel("Изменение NPV, млн ₽")
    ax.set_title("Чувствительность NPV к допущениям", fontsize=13, fontweight="bold",
                 color=NAVY, pad=14, loc="left")
    ax.set_xlim(-165, 165)
    ax.xaxis.grid(True, color=RULE, lw=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="lower right", fontsize=9)
    fig.tight_layout()
    out = HERE / "assets" / "tornado.png"
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


if __name__ == "__main__":
    for path in (waterfall(), tornado()):
        print("wrote", path.relative_to(HERE.parent))
