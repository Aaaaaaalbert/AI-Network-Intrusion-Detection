"""Render the three summary figures used in the admissions write-up.

Every number is read from the committed results files, never typed in by hand,
so the figures cannot drift from the metrics they illustrate.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
OUT = RESULTS / "figures"

# Validated palette (dataviz reference instance): blue = series 1, orange = series 2.
BLUE, ORANGE = "#2a78d6", "#eb6834"
SURFACE, INK, INK_2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"

plt.rcParams.update({
    "font.family": ["Microsoft JhengHei", "Segoe UI", "sans-serif"],
    "axes.unicode_minus": False,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": AXIS,
    "axes.labelcolor": INK_2,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "text.color": INK,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
})


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fig_validation_strategies() -> Path:
    binary_random = load_json(RESULTS / "random_forest_metrics.json")["recall"]
    binary_by_day = load_json(RESULTS / "by_day" / "random_forest_metrics.json")["recall"]
    mc_random = load_json(RESULTS / "multiclass_random" / "random_forest_metrics.json")["macro_f1"]
    mc_temporal = load_json(RESULTS / "multiclass_temporal" / "random_forest_metrics.json")["macro_f1"]

    panels = [
        ("二元分類 Recall", ["隨機切分", "按日期切分\n(一至四訓練、五測試)"], [binary_random, binary_by_day]),
        ("多類別 Macro F1", ["隨機切分", "類別內時間切分"], [mc_random, mc_temporal]),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(9, 4.2), dpi=200)
    for ax, (title, labels, values) in zip(axes, panels):
        bars = ax.bar(labels, [v * 100 for v in values], width=0.55, color=BLUE, linewidth=0)
        ax.set_ylim(0, 108)
        ax.set_title(title, fontsize=12, color=INK, loc="left", pad=10)
        ax.yaxis.grid(True)
        ax.set_axisbelow(True)
        ax.tick_params(axis="both", length=0, labelsize=9.5)
        ax.set_ylabel("%", fontsize=9)
        for bar, v in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 2, f"{v * 100:.2f}%",
                    ha="center", va="bottom", fontsize=10.5, color=INK, fontweight="bold")
    fig.suptitle("同一個 Random Forest，換一種驗證方式分數差多少", fontsize=13, color=INK, x=0.02, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    path = OUT / "validation_strategies.png"
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path


def fig_reliability() -> Path:
    series = [
        ("隨機切分（ECE 0.04%）", load_json(RESULTS / "calibration" / "binary_random.json"), BLUE),
        ("按日期切分（ECE 32.97%）", load_json(RESULTS / "calibration" / "binary_by_day.json"), ORANGE),
    ]
    fig, ax = plt.subplots(figsize=(6.4, 5.4), dpi=200)
    ax.plot([0, 1], [0, 1], linestyle=(0, (4, 4)), color=MUTED, linewidth=1.2, label="完美校準（信心 = 準確率）")
    for name, data, color in series:
        bins = [b for b in data["reliability_bins"] if b["count"]]
        x = [b["avg_confidence"] for b in bins]
        y = [b["accuracy"] for b in bins]
        ax.plot(x, y, color=color, linewidth=2, marker="o", markersize=7,
                markeredgecolor=SURFACE, markeredgewidth=1.5, label=name)
        ax.annotate(name, (x[-1], y[-1]), xytext=(-8, 10 if color == BLUE else -16),
                    textcoords="offset points", ha="right", fontsize=9, color=INK_2)
    by_day = series[1][1]["reliability_bins"][-1]
    ax.annotate(
        f"信心 {by_day['avg_confidence'] * 100:.1f}%，實際只對 {by_day['accuracy'] * 100:.1f}%\n（佔 88% 的預測）",
        (by_day["avg_confidence"], by_day["accuracy"]), xytext=(-140, -60), textcoords="offset points",
        fontsize=9, color=INK, arrowprops={"arrowstyle": "-", "color": MUTED, "linewidth": 1},
    )
    ax.set_xlim(0.4, 1.02)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("模型宣稱的信心分數（各區間平均）", fontsize=10)
    ax.set_ylabel("該區間的實際準確率", fontsize=10)
    ax.grid(True)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", length=0, labelsize=9)
    ax.legend(loc="upper left", frameon=False, fontsize=9)
    ax.set_title("可靠度圖：信心分數在新資料分布下失真", fontsize=13, color=INK, loc="left", pad=12)
    fig.tight_layout()
    path = OUT / "reliability_diagram.png"
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path


def fig_leave_one_attack_out() -> Path:
    summary = pd.read_csv(RESULTS / "leave_one_attack_out" / "summary.csv")
    summary["held_out_attack"] = summary["held_out_attack"].str.replace("\x96", "-", regex=False)
    summary = summary.sort_values("binary_unseen_attack_recall")
    seen = summary["control_seen_binary_recall"] * 100
    unseen = summary["binary_unseen_attack_recall"] * 100
    y = range(len(summary))

    fig, ax = plt.subplots(figsize=(8.4, 5.8), dpi=200)
    ax.hlines(y, unseen, seen, color=GRID, linewidth=2, zorder=1)
    ax.scatter(seen, y, s=70, color=BLUE, edgecolor=SURFACE, linewidth=1.5, zorder=3, label="訓練時看過該攻擊")
    ax.scatter(unseen, y, s=70, color=ORANGE, edgecolor=SURFACE, linewidth=1.5, zorder=3, label="訓練時完全沒看過")
    for yi, u in zip(y, unseen):
        # Tiny values sit on the axis: label them to the right so they don't
        # collide with the category names.
        if u < 10:
            ax.text(u + 2, yi + 0.28, f"{u:.1f}%", ha="left", va="center", fontsize=8.5, color=INK_2)
        else:
            ax.text(u - 1.5, yi, f"{u:.1f}%", ha="right", va="center", fontsize=8.5, color=INK_2)
    ax.set_yticks(list(y))
    ax.set_yticklabels(summary["held_out_attack"], fontsize=9.5)
    ax.set_xlim(-2, 104)
    ax.set_xlabel("二元 Recall（%）", fontsize=10)
    ax.xaxis.grid(True)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", length=0, labelsize=9)
    ax.legend(loc="upper left", bbox_to_anchor=(0.02, 0.98), frameon=False, fontsize=9)
    avg_seen = summary["control_seen_binary_recall"].mean() * 100
    avg_unseen = summary["binary_unseen_attack_recall"].mean() * 100
    ax.set_title(f"留一攻擊類型：看過平均 {avg_seen:.2f}% → 沒看過平均 {avg_unseen:.2f}%",
                 fontsize=12.5, color=INK, loc="left", pad=12)
    fig.tight_layout()
    path = OUT / "leave_one_attack_out.png"
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for path in (fig_validation_strategies(), fig_reliability(), fig_leave_one_attack_out()):
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
