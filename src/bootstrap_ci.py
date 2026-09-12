"""Paired test-set bootstrap CIs for the six split x feature-ablation runs.

Rows inside one (true, pred_Full, pred_MinusPort, pred_MinusTCPwindow) cell are
exchangeable for every confusion-matrix statistic, so resampling test rows is
equivalent to a multinomial draw over those cells. Variants inside one split
share the identical test set and are resampled jointly (paired); the two splits
have different test sets and are resampled independently.

Quantifies test-set sampling noise only. It does not capture training
randomness, which would need repeated seeds.
"""
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd

SPLITS = ['Random_Stratified', 'Temporal']
VARIANTS = ['Full', 'Minus_Port', 'Minus_TCP_window']


def macro_f1(cm):
    """Macro F1 from a stack of confusion matrices (..., C, C); rows are truth."""
    tp = np.diagonal(cm, axis1=-2, axis2=-1)
    fn = cm.sum(-1) - tp
    fp = cm.sum(-2) - tp
    denom = 2 * tp + fp + fn
    f1 = np.divide(2 * tp, denom, out=np.zeros(denom.shape, float), where=denom > 0)
    return f1.mean(-1)


def accuracy(cm):
    return np.diagonal(cm, axis1=-2, axis2=-1).sum(-1) / cm.sum((-2, -1))


def load_split(root, split, labels):
    """Return (n_rows, cell_counts, cell_codes) for the paired cell encoding."""
    codes, base = None, None
    index = {l: i for i, l in enumerate(labels)}
    for variant in VARIANTS:
        df = pd.read_csv(root / f'{split}_{variant}' / 'predictions.csv')
        if base is None:
            base = df.row_id.values
            codes = df.label.map(index).to_numpy()
        else:
            assert np.array_equal(df.row_id.values, base), f'{split}/{variant} test rows differ'
        codes = codes * len(labels) + df.prediction.map(index).to_numpy()
    cells, counts = np.unique(codes, return_counts=True)
    return len(codes), counts, cells


def unpack(cells, labels):
    """Split packed (true, p_Full, p_Port, p_TCP) codes into one column each."""
    c = len(labels)
    out = []
    for _ in range(len(VARIANTS) + 1):
        out.append(cells % c)
        cells = cells // c
    return out[::-1]


def confusions(counts, truth, preds, n_labels):
    """counts (..., K) -> confusion matrices (..., C, C) via bincount on flat cells."""
    flat = truth * n_labels + preds
    shape = counts.shape[:-1]
    out = np.zeros(shape + (n_labels * n_labels,))
    for idx in np.ndindex(shape):
        out[idx] = np.bincount(flat, weights=counts[idx], minlength=n_labels * n_labels)
    return out.reshape(shape + (n_labels, n_labels))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--results-dir', type=Path, default=Path('results/tanet_split_ablation'))
    parser.add_argument('--iterations', type=int, default=10000)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    root = args.results_dir
    labels = json.loads((root / 'config.json').read_text())['labels']
    n_labels = len(labels)
    rng = np.random.default_rng(args.seed)

    point, draws = {}, {}
    for split in SPLITS:
        n, counts, cells = load_split(root, split, labels)
        truth, *pred_cols = unpack(cells, labels)
        print(f'{split}: {n} test rows, {len(cells)} distinct outcome cells', flush=True)
        sample = rng.multinomial(n, counts / n, size=args.iterations)
        for variant, preds in zip(VARIANTS, pred_cols):
            observed = confusions(counts[None, :], truth, preds, n_labels)[0]
            point[(split, variant)] = dict(macro_f1=macro_f1(observed), accuracy=accuracy(observed))
            boot = confusions(sample, truth, preds, n_labels)
            draws[(split, variant)] = dict(macro_f1=macro_f1(boot), accuracy=accuracy(boot))
            print(f'  {variant}: macro F1 {point[(split, variant)]["macro_f1"]:.6f}', flush=True)

    def summarize(name, observed, sample):
        lo, hi = np.percentile(sample, [2.5, 97.5])
        return dict(quantity=name, point=observed, ci_low=lo, ci_high=hi,
                    std_error=sample.std(ddof=1), excludes_zero=bool(lo > 0 or hi < 0))

    rows = []
    for (split, variant), stats in point.items():
        for metric in ('macro_f1', 'accuracy'):
            rows.append(dict(kind='metric', split=split, variant=variant,
                             **summarize(metric, stats[metric], draws[(split, variant)][metric])))
    # Paired ablation deltas: same test rows, same resample, so difference is paired.
    for split in SPLITS:
        for variant in VARIANTS[1:]:
            d_point = point[(split, variant)]['macro_f1'] - point[(split, 'Full')]['macro_f1']
            d_draws = draws[(split, variant)]['macro_f1'] - draws[(split, 'Full')]['macro_f1']
            rows.append(dict(kind='ablation_delta', split=split, variant=variant,
                             **summarize(f'macro_f1({variant}) - macro_f1(Full)', d_point, d_draws)))
    # Interaction: the two splits have different test sets, so their draws are independent.
    for variant in VARIANTS[1:]:
        def delta(split, src):
            return src[(split, variant)]['macro_f1'] - src[(split, 'Full')]['macro_f1']
        i_point = delta('Random_Stratified', point) - delta('Temporal', point)
        i_draws = delta('Random_Stratified', draws) - delta('Temporal', draws)
        rows.append(dict(kind='interaction', split='Random_minus_Temporal', variant=variant,
                         **summarize(f'delta_Random - delta_Temporal ({variant})', i_point, i_draws)))

    table = pd.DataFrame(rows)
    table.to_csv(root / 'bootstrap_ci.csv', index=False)
    (root / 'bootstrap_config.json').write_text(json.dumps(
        dict(iterations=args.iterations, seed=args.seed, method='paired multinomial cell bootstrap',
             captures='test-set sampling variability only; not training randomness'), indent=2))
    pd.set_option('display.width', 200, 'display.max_colwidth', 60)
    print(table.to_string(index=False, float_format=lambda v: f'{v:.6f}'))


if __name__ == '__main__':
    main()
