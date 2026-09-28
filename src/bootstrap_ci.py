"""Test-set bootstrap CIs for the six split x feature-ablation runs.

Two resampling schemes, because the quantities need different ones.

Within one split, the three variants share the identical test set, so rows in
one (true, pred_Full, pred_MinusPort, pred_MinusTCPwindow) cell are
exchangeable and resampling test rows is a multinomial draw over those cells.
The variants are resampled jointly, which pairs the ablation deltas.

Across the two splits the test sets are NOT independent: they overlap by
113,076 rows (19.97% of each). An earlier version of this script drew the two
splits' bootstraps independently and subtracted them, which misstates the
variance of the interaction. The joint scheme below resamples the union of the
two test sets once, so a shared row carries the same multiplicity into both
splits and the covariance is preserved. Both interaction estimates are
reported so the size of the correction is visible.

Neither scheme covers correlation between flows from the same attack scenario,
nor training randomness (see src/multiseed_ablation.py for the latter).
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


def predictions(root, split, variant):
    return pd.read_csv(root / f'{split}_{variant}' / 'predictions.csv')


def load_split(root, split, labels):
    """Within-split encoding: (n_rows, cell_counts, packed_cell_codes)."""
    codes, base = None, None
    index = {l: i for i, l in enumerate(labels)}
    for variant in VARIANTS:
        df = predictions(root, split, variant)
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


def load_union(root, labels):
    """Union of both test sets, one column per (split, variant), sentinel where absent.

    Rows sharing a full outcome signature are exchangeable for every statistic
    computed here, so the union collapses to a few hundred cells.
    """
    index = {l: i for i, l in enumerate(labels)}
    columns, truths = {}, []
    for split in SPLITS:
        for variant in VARIANTS:
            df = predictions(root, split, variant)
            columns[(split, variant)] = pd.Series(df.prediction.map(index).values, index=df.row_id.values)
        truths.append(pd.Series(df.label.map(index).values, index=df.row_id.values))
    combined = pd.DataFrame(columns)  # outer-joins on row_id
    truth = pd.concat(truths)
    truth = truth[~truth.index.duplicated()]
    combined.insert(0, 'truth', truth)
    overlap = int(combined.notna().all(axis=1).sum())
    signatures, counts = np.unique(combined.fillna(len(labels)).to_numpy(np.int16), axis=0, return_counts=True)
    order = [(split, variant) for split in SPLITS for variant in VARIANTS]
    return len(combined), overlap, counts, signatures, order


def confusions_from_signatures(draws, signatures, column, n_labels):
    """Confusion matrices for one variant, ignoring rows outside its split."""
    pred = signatures[:, column].astype(int)
    present = pred != n_labels
    flat = signatures[present, 0].astype(int) * n_labels + pred[present]
    indicator = np.zeros((present.sum(), n_labels * n_labels))
    indicator[np.arange(present.sum()), flat] = 1.0
    return (draws[:, present] @ indicator).reshape(-1, n_labels, n_labels)


def summarize(name, observed, sample):
    lo, hi = np.percentile(sample, [2.5, 97.5])
    return dict(quantity=name, point=observed, ci_low=lo, ci_high=hi,
                std_error=sample.std(ddof=1), excludes_zero=bool(lo > 0 or hi < 0))


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

    rows = []
    for (split, variant), stats in point.items():
        for metric in ('macro_f1', 'accuracy'):
            rows.append(dict(kind='metric', split=split, variant=variant,
                             **summarize(metric, stats[metric], draws[(split, variant)][metric])))
    for split in SPLITS:
        for variant in VARIANTS[1:]:
            d_point = point[(split, variant)]['macro_f1'] - point[(split, 'Full')]['macro_f1']
            d_draws = draws[(split, variant)]['macro_f1'] - draws[(split, 'Full')]['macro_f1']
            rows.append(dict(kind='ablation_delta', split=split, variant=variant,
                             **summarize(f'macro_f1({variant}) - macro_f1(Full)', d_point, d_draws)))

    # Superseded scheme, kept only to show how far the independence assumption was off.
    for variant in VARIANTS[1:]:
        def delta(split, src):
            return src[(split, variant)]['macro_f1'] - src[(split, 'Full')]['macro_f1']
        i_point = delta('Random_Stratified', point) - delta('Temporal', point)
        i_draws = delta('Random_Stratified', draws) - delta('Temporal', draws)
        rows.append(dict(kind='interaction_independent_superseded', split='Random_minus_Temporal', variant=variant,
                         **summarize(f'delta_Random - delta_Temporal ({variant})', i_point, i_draws)))

    n_union, overlap, counts, signatures, order = load_union(root, labels)
    print(f'\njoint: {n_union} union rows, {overlap} shared by both test sets '
          f'({overlap / n_union * 100:.2f}% of the union), {len(signatures)} signatures', flush=True)
    joint = rng.multinomial(n_union, counts / n_union, size=args.iterations)
    observed = counts[None, :]
    joint_f1, point_f1 = {}, {}
    for column, key in enumerate(order, start=1):
        joint_f1[key] = macro_f1(confusions_from_signatures(joint, signatures, column, n_labels))
        point_f1[key] = macro_f1(confusions_from_signatures(observed, signatures, column, n_labels))[0]

    for variant in VARIANTS[1:]:
        def delta(split, src):
            return src[(split, variant)] - src[(split, 'Full')]
        i_point = delta('Random_Stratified', point_f1) - delta('Temporal', point_f1)
        i_draws = delta('Random_Stratified', joint_f1) - delta('Temporal', joint_f1)
        correlation = np.corrcoef(delta('Random_Stratified', joint_f1), delta('Temporal', joint_f1))[0, 1]
        entry = summarize(f'delta_Random - delta_Temporal ({variant}), joint resampling', i_point, i_draws)
        entry['delta_correlation'] = correlation
        rows.append(dict(kind='interaction_joint', split='Random_minus_Temporal', variant=variant, **entry))

    table = pd.DataFrame(rows)
    table.to_csv(root / 'bootstrap_ci.csv', index=False)
    (root / 'bootstrap_config.json').write_text(json.dumps(dict(
        iterations=args.iterations, seed=args.seed,
        within_split='paired multinomial over shared-test-set outcome cells',
        across_split='joint multinomial over the union of both test sets, preserving the shared rows',
        union_rows=n_union, overlapping_rows=overlap, signature_cells=int(len(signatures)),
        not_covered=['same-scenario flow correlation', 'training randomness', 'resampling of the split itself'],
    ), indent=2))
    pd.set_option('display.width', 220, 'display.max_colwidth', 46)
    print(table.to_string(index=False, float_format=lambda v: f'{v:.6f}'))


if __name__ == '__main__':
    main()
