"""Repeat the port ablation across training seeds with the split held fixed.

The bootstrap in src/bootstrap_ci.py covers test-set sampling only. This script
covers the other half: it reuses the exact train/test indices from the main run,
so the split, the preprocessor and the test support are identical across seeds
and the only thing that varies is the Random Forest's own randomness.

Four cells (two splits x {Full, Minus_Port}) x N seeds. Seed 42 is read back
from the main run rather than retrained. Every finished cell is written out
immediately, so an interrupted run resumes where it stopped.
"""
from pathlib import Path
import argparse
import gc
import hashlib
import json
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

from src.prepare_data import load_csv_directory, clean_data, build_preprocessor, NON_FEATURE_COLUMNS
from src.train_baseline import MODELS

SPLITS = ['Random_Stratified', 'Temporal']
VARIANTS = {'Full': [], 'Minus_Port': ['source_port', 'destination_port']}


def model_params(seed):
    """Main-run Random Forest settings with only random_state changed."""
    params = MODELS['random_forest']().get_params()
    baseline = dict(n_estimators=100, class_weight='balanced', random_state=42)
    for key, value in baseline.items():
        assert params[key] == value, f'train_baseline changed {key}: {params[key]!r} != {value!r}'
    return {**params, 'random_state': seed}


def evaluate(model, x_test, y_test, labels):
    pred = model.predict(x_test)
    report = classification_report(y_test, pred, labels=labels, output_dict=True, zero_division=0)
    return pred, dict(accuracy=accuracy_score(y_test, pred),
                      macro_precision=report['macro avg']['precision'],
                      macro_recall=report['macro avg']['recall'],
                      macro_f1=report['macro avg']['f1-score'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--main-dir', type=Path, default=Path('results/tanet_split_ablation'))
    parser.add_argument('--output-dir', type=Path, default=Path('results/tanet_multiseed'))
    parser.add_argument('--seeds', type=int, nargs='+', default=[42, 43, 44])
    args = parser.parse_args()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    main_config = json.loads((args.main_dir / 'config.json').read_text())
    labels, features = main_config['labels'], main_config['features']

    todo = [(s, v, seed) for s in SPLITS for v in VARIANTS for seed in args.seeds
            if seed != 42 and not (out / f'{s}_{v}_seed{seed}.json').exists()]
    print(f'{len(todo)} cells to train: {todo}', flush=True)

    if todo:
        print('Loading and cleaning original data', flush=True)
        data = clean_data(load_csv_directory(Path('dataset/raw')))
        fingerprint = hashlib.sha256(pd.util.hash_pandas_object(data, index=True).values.tobytes()).hexdigest()
        assert fingerprint == main_config['data_sha256'], 'Data differs from the main run; indices would not align'
        assert [c for c in data if c not in NON_FEATURE_COLUMNS | {'label', 'is_attack'}] == features

        for split in SPLITS:
            pending = [(v, seed) for (s, v, seed) in todo if s == split]
            if not pending:
                continue
            # Reusing the main run's indices is what keeps the split fixed across seeds.
            indices = np.load(args.main_dir / f'{split}_indices.npz')
            train, test = data.loc[indices['train']], data.loc[indices['test']]
            assert not set(train.index) & set(test.index)
            print(f'{split}: preprocessing {len(train)} train / {len(test)} test', flush=True)
            pre = build_preprocessor(train[features])
            x_train = pd.DataFrame(pre.fit_transform(train[features]), columns=pre.get_feature_names_out())
            x_test = pd.DataFrame(pre.transform(test[features]), columns=pre.get_feature_names_out())
            for variant, seed in pending:
                drop = VARIANTS[variant]
                cols = [c for c in x_train if c not in drop]
                print(f'Training {split} {variant} seed={seed}', flush=True)
                started = time.time()
                model = RandomForestClassifier(**model_params(seed)).fit(x_train[cols], train.label)
                pred, metrics = evaluate(model, x_test[cols], test.label, labels)
                metrics.update(split=split, feature_set=variant, seed=seed, train_rows=len(train),
                               test_rows=len(test), dropped_columns=drop, fit_seconds=round(time.time() - started, 1))
                (out / f'{split}_{variant}_seed{seed}.json').write_text(json.dumps(metrics, indent=2))
                pd.DataFrame(confusion_matrix(test.label, pred, labels=labels), index=labels, columns=labels) \
                    .to_csv(out / f'{split}_{variant}_seed{seed}_confusion_matrix.csv')
                print(json.dumps(metrics), flush=True)
                del model, pred
                gc.collect()
            del x_train, x_test, train, test, pre
            gc.collect()
        del data
        gc.collect()

    rows = []
    for split in SPLITS:
        for variant in VARIANTS:
            for seed in args.seeds:
                if seed == 42:
                    source = json.loads((args.main_dir / f'{split}_{variant}' / 'metrics.json').read_text())
                    rows.append(dict(split=split, feature_set=variant, seed=42,
                                     macro_f1=source['macro_f1'], accuracy=source['accuracy']))
                else:
                    source = json.loads((out / f'{split}_{variant}_seed{seed}.json').read_text())
                    rows.append(dict(split=split, feature_set=variant, seed=seed,
                                     macro_f1=source['macro_f1'], accuracy=source['accuracy']))
    runs = pd.DataFrame(rows)
    runs.to_csv(out / 'runs.csv', index=False)

    wide = runs.pivot_table(index=['split', 'seed'], columns='feature_set', values='macro_f1')
    wide['delta_pp'] = (wide['Minus_Port'] - wide['Full']) * 100
    summary = wide.groupby('split')['delta_pp'].agg(['mean', 'std', 'min', 'max', 'count'])
    interaction = wide.xs('Random_Stratified')['delta_pp'] - wide.xs('Temporal')['delta_pp']
    wide.to_csv(out / 'per_seed_delta.csv')
    summary.to_csv(out / 'delta_summary.csv')
    print('\n=== macro F1 by seed ===')
    print((wide[['Full', 'Minus_Port']] * 100).round(4).to_string())
    print('\n=== -Port delta (pp) by split ===')
    print(summary.round(4).to_string())
    print('\n=== interaction (Random - Temporal, pp), paired by seed ===')
    print(interaction.round(4).to_string())
    print(f'mean {interaction.mean():.4f}  std {interaction.std(ddof=1):.4f}  '
          f'min {interaction.min():.4f}  max {interaction.max():.4f}')


if __name__ == '__main__':
    main()
