"""One consistent look for every chart written by the experiments."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # write image files; no window needed

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BLUE = "#2a78d6"    # first series: the method or measurement the chart is about
ORANGE = "#eb6834"  # second series: what it is compared with


def _font() -> str:
    for name in ("Helvetica Neue", "Segoe UI", "Arial"):
        try:
            font_manager.findfont(name, fallback_to_default=False)
            return name
        except ValueError:
            continue
    return "DejaVu Sans"


plt.rcParams["font.family"] = _font()


def new_chart(title: str, subtitle: str = "", width: float = 7.4, height: float = 4.4):
    figure, axes = plt.subplots(figsize=(width, height), dpi=160)
    figure.patch.set_facecolor(SURFACE)
    axes.set_facecolor(SURFACE)
    for side in ("top", "right"):
        axes.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axes.spines[side].set_color(AXIS)
        axes.spines[side].set_linewidth(0.8)
    axes.grid(axis="y", color=GRID, linewidth=0.8)
    axes.set_axisbelow(True)
    axes.tick_params(colors=INK_MUTED, labelsize=9, length=0)
    figure.suptitle(title, x=0.02, y=0.98, ha="left", va="top", fontsize=12.5, fontweight="bold", color=INK)
    if subtitle:
        figure.text(0.02, 0.905, subtitle, ha="left", va="top", fontsize=9.5, color=INK_SECONDARY)
    figure.subplots_adjust(top=0.80 if subtitle else 0.88, left=0.10, right=0.95, bottom=0.13)
    return figure, axes


def axis_labels(axes, x: str = "", y: str = "") -> None:
    axes.set_xlabel(x, fontsize=9.5, color=INK_SECONDARY, labelpad=8)
    axes.set_ylabel(y, fontsize=9.5, color=INK_SECONDARY, labelpad=8)


def line(axes, x, y, colour: str, label: str, markers: bool = True):
    return axes.plot(x, y, color=colour, linewidth=2, label=label, solid_capstyle="round", solid_joinstyle="round",
                     marker="o" if markers else None, markersize=7, markeredgecolor=SURFACE, markeredgewidth=1.5)


def legend(axes, **options) -> None:
    box = axes.legend(frameon=False, fontsize=9.5, handlelength=1.6, **options)
    for text in box.get_texts():
        text.set_color(INK_SECONDARY)


def save(figure, path: Path) -> Path:
    path.parent.mkdir(exist_ok=True)
    figure.savefig(path, facecolor=SURFACE)
    plt.close(figure)
    return path
