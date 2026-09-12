"""Single-column (7.6 cm) versions of the paper figures for the TANET template.

The conference format puts captions in the document text below the figure, so
these carry no in-image title, and the type is sized to stay legible after the
image is scaled into a 7.6 cm column.
"""
from pathlib import Path
import argparse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams.update({'font.family': 'Microsoft JhengHei', 'axes.unicode_minus': False, 'font.size': 7.5})
SPLIT_LABEL = {'Random_Stratified': '隨機分層', 'Temporal': '類別內時間'}
VARIANT_LABEL = {'Full': '全特徵', 'Minus_Port': '移除 Port', 'Minus_TCP_window': '移除 TCP window'}
COLORS = {'Full': '#3B6EA5', 'Minus_Port': '#C4553B', 'Minus_TCP_window': '#7A9A5B'}
FIGSIZE = (3.35, 2.45)


def pick(ci, kind, split, variant):
    row = ci[(ci['kind'] == kind) & (ci['split'] == split) & (ci['variant'] == variant)]
    if kind == 'metric':
        row = row[row['quantity'] == 'macro_f1']
    return row.iloc[0]


def tidy(ax):
    ax.grid(axis='y', alpha=0.25, lw=0.6)
    ax.set_axisbelow(True)
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)


def figure_macro_f1(ci, path):
    fig, ax = plt.subplots(figsize=FIGSIZE)
    width, xs = 0.26, np.arange(len(SPLIT_LABEL))
    for i, variant in enumerate(VARIANT_LABEL):
        pts = [pick(ci, 'metric', s, variant) for s in SPLIT_LABEL]
        values = np.array([p['point'] for p in pts]) * 100
        err = np.array([[p['point'] - p['ci_low'] for p in pts],
                        [p['ci_high'] - p['point'] for p in pts]]) * 100
        pos = xs + (i - 1) * width
        ax.bar(pos, values, width, label=VARIANT_LABEL[variant], color=COLORS[variant], edgecolor='white', lw=0.4)
        ax.errorbar(pos, values, yerr=err, fmt='none', ecolor='#2A2A2A', capsize=2, lw=0.8)
        for x, v in zip(pos, values):
            ax.text(x, v - 1.2, f'{v:.1f}', ha='center', va='top', fontsize=6, color='white')
    ax.set_xticks(xs, [SPLIT_LABEL[s] for s in SPLIT_LABEL])
    ax.set_ylabel('Macro F1 (%)', fontsize=7.5)
    ax.set_ylim(60, 100)
    ax.legend(frameon=False, ncol=3, fontsize=6, loc='lower center',
              bbox_to_anchor=(0.5, -0.28), columnspacing=1.0, handlelength=1.2)
    tidy(ax)
    fig.savefig(path, dpi=400, bbox_inches='tight', pad_inches=0.02)
    plt.close(fig)


def figure_interaction(ci, path):
    fig, ax = plt.subplots(figsize=FIGSIZE)
    xs = np.arange(len(SPLIT_LABEL))
    # Port labels sit left of the marker so they clear its tall error bar.
    offsets = {'Minus_Port': ((-7, -3), 'right'), 'Minus_TCP_window': ((0, -14), 'center')}
    for variant, marker in zip(['Minus_Port', 'Minus_TCP_window'], ['o', 's']):
        pts = [pick(ci, 'ablation_delta', s, variant) for s in SPLIT_LABEL]
        values = np.array([p['point'] for p in pts]) * 100
        err = np.array([[p['point'] - p['ci_low'] for p in pts],
                        [p['ci_high'] - p['point'] for p in pts]]) * 100
        ax.errorbar(xs, values, yerr=err, marker=marker, ms=4.5, lw=1.4, capsize=3,
                    color=COLORS[variant], label=VARIANT_LABEL[variant])
        for x, v in zip(xs, values):
            shift, align = offsets[variant]
            ax.annotate(f'{v:+.2f}', (x, v), textcoords='offset points', ha=align,
                        xytext=shift, fontsize=6.5, color=COLORS[variant])
    ax.axhline(0, color='#555', lw=0.8, ls='--')
    ax.set_xticks(xs, [SPLIT_LABEL[s] for s in SPLIT_LABEL])
    ax.set_xlim(-0.35, 1.35)
    ax.set_ylim(-8.5, 10.5)
    ax.set_ylabel('Macro F1 變化（百分點）', fontsize=7.5)
    ax.legend(frameon=False, fontsize=6.5, loc='lower right', handlelength=1.4)
    tidy(ax)
    fig.savefig(path, dpi=400, bbox_inches='tight', pad_inches=0.02)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--results-dir', type=Path, default=Path('results/tanet_split_ablation'))
    parser.add_argument('--figure-dir', type=Path, default=Path('results/figures'))
    args = parser.parse_args()
    ci = pd.read_csv(args.results_dir / 'bootstrap_ci.csv')
    figure_macro_f1(ci, args.figure_dir / 'paper_fig1_col.png')
    figure_interaction(ci, args.figure_dir / 'paper_fig2_col.png')
    print('wrote paper_fig1_col.png and paper_fig2_col.png')


if __name__ == '__main__':
    main()
