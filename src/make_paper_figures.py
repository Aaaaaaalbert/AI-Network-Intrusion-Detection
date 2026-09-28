"""Two TANET paper figures: six-run macro F1 with CIs, and the ablation interaction."""
from pathlib import Path
import argparse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams.update({'font.family': 'Microsoft JhengHei', 'axes.unicode_minus': False, 'font.size': 11})
SPLIT_LABEL = {'Random_Stratified': '隨機分層切分', 'Temporal': '類別內時間切分'}
VARIANT_LABEL = {'Full': '全特徵', 'Minus_Port': '移除 Port', 'Minus_TCP_window': '移除 TCP window'}
COLORS = {'Full': '#3B6EA5', 'Minus_Port': '#C4553B', 'Minus_TCP_window': '#7A9A5B'}


def pick(ci, kind, split, variant):
    row = ci[(ci['kind'] == kind) & (ci['split'] == split) & (ci['variant'] == variant)]
    if kind == 'metric':
        row = row[row['quantity'] == 'macro_f1']
    return row.iloc[0]


def figure_macro_f1(ci, path):
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    width, xs = 0.26, np.arange(len(SPLIT_LABEL))
    for i, variant in enumerate(VARIANT_LABEL):
        pts = [pick(ci, 'metric', s, variant) for s in SPLIT_LABEL]
        values = np.array([p['point'] for p in pts]) * 100
        err = np.array([[p['point'] - p['ci_low'] for p in pts],
                        [p['ci_high'] - p['point'] for p in pts]]) * 100
        pos = xs + (i - 1) * width
        ax.bar(pos, values, width, label=VARIANT_LABEL[variant], color=COLORS[variant], edgecolor='white')
        ax.errorbar(pos, values, yerr=err, fmt='none', ecolor='#2A2A2A', capsize=4, lw=1.2)
        for x, v in zip(pos, values):
            ax.text(x, v - 1.6, f'{v:.2f}', ha='center', va='top', fontsize=9, color='white')
    ax.set_xticks(xs, [SPLIT_LABEL[s] for s in SPLIT_LABEL])
    ax.set_ylabel('Macro F1 (%)')
    ax.set_ylim(60, 102)
    ax.set_title('圖 1　六組實驗的 Macro F1（誤差棒為測試集 bootstrap 95% 信賴區間）', fontsize=11, pad=12)
    ax.legend(frameon=False, ncol=3, loc='lower center', bbox_to_anchor=(0.5, -0.22))
    ax.grid(axis='y', alpha=0.25)
    ax.set_axisbelow(True)
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)


def figure_interaction(ci, path):
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    xs = np.arange(len(SPLIT_LABEL))
    offsets = {'Minus_Port': (12, -4), 'Minus_TCP_window': (12, -18)}
    for variant, marker in zip(['Minus_Port', 'Minus_TCP_window'], ['o', 's']):
        pts = [pick(ci, 'ablation_delta', s, variant) for s in SPLIT_LABEL]
        values = np.array([p['point'] for p in pts]) * 100
        err = np.array([[p['point'] - p['ci_low'] for p in pts],
                        [p['ci_high'] - p['point'] for p in pts]]) * 100
        ax.errorbar(xs, values, yerr=err, marker=marker, ms=8, lw=2, capsize=5,
                    color=COLORS[variant], label=VARIANT_LABEL[variant])
        for x, v in zip(xs, values):
            ax.annotate(f'{v:+.2f} pp', (x, v), textcoords='offset points',
                        xytext=offsets[variant], fontsize=9, color=COLORS[variant])
    ax.axhline(0, color='#555', lw=1, ls='--')
    ax.set_xticks(xs, [SPLIT_LABEL[s] for s in SPLIT_LABEL])
    ax.set_xlim(-0.4, 1.55)
    ax.set_ylabel('Macro F1 相對全特徵的變化（百分點）')
    inter = pick(ci, 'interaction_joint', 'Random_minus_Temporal', 'Minus_Port')
    ax.set_title('圖 2　特徵消融效果隨切分策略反轉\n'
                 f'移除 Port 的切分間差異 {inter["point"] * 100:.2f} pp'
                 f'（95% CI [{inter["ci_low"] * 100:.2f}, {inter["ci_high"] * 100:.2f}]）',
                 fontsize=11, pad=12)
    ax.legend(frameon=False, loc='upper left')
    ax.grid(axis='y', alpha=0.25)
    ax.set_axisbelow(True)
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--results-dir', type=Path, default=Path('results/tanet_split_ablation'))
    parser.add_argument('--figure-dir', type=Path, default=Path('results/figures'))
    args = parser.parse_args()
    ci = pd.read_csv(args.results_dir / 'bootstrap_ci.csv')
    args.figure_dir.mkdir(parents=True, exist_ok=True)
    figure_macro_f1(ci, args.figure_dir / 'paper_fig1_macro_f1.png')
    figure_interaction(ci, args.figure_dir / 'paper_fig2_interaction.png')
    print('wrote paper_fig1_macro_f1.png and paper_fig2_interaction.png')


if __name__ == '__main__':
    main()
