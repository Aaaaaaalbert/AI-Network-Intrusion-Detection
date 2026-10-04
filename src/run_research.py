"""Reproducible 15-label split x feature ablation; preserves historical artifacts."""
from pathlib import Path
import gc
import hashlib
import json
import argparse
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from src.prepare_data import load_csv_directory, clean_data, split_temporal_per_class, build_preprocessor, NON_FEATURE_COLUMNS
from src.train_baseline import MODELS

GROUPS = {'Full': [], 'Minus_Port': ['source_port', 'destination_port'],
          'Minus_TCP_window': ['init_win_bytes_forward', 'init_win_bytes_backward']}

def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=True, indent=2), encoding='utf-8')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, default=Path('results/tanet_split_ablation'))
    args = parser.parse_args()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    print('Loading and cleaning original data', flush=True)
    data = clean_data(load_csv_directory(Path('dataset/raw')))
    labels = sorted(data.label.unique())
    assert len(labels) == 15
    features = [c for c in data if c not in NON_FEATURE_COLUMNS | {'label', 'is_attack'}]
    diagnostics = []
    for label, g in data.groupby('label'):
        a, b = g.source_ip.astype(str).str.strip(), g.destination_ip.astype(str).str.strip()
        directed = pd.Series(list(zip(a, b)), index=g.index)
        undirected = pd.Series(list(zip(np.minimum(a, b), np.maximum(a, b))), index=g.index)
        counts = undirected.value_counts()
        diagnostics.append(dict(label=label, support=len(g), missing_ip_rows=int(g[['source_ip','destination_ip']].isna().any(axis=1).sum()),
            directed_ip_pairs=directed.nunique(), undirected_ip_pairs=undirected.nunique(),
            major_pair_rows=int(counts.iloc[0]), major_pair_fraction=float(counts.iloc[0]/len(g)),
            five_tuple_groups=g[['source_ip','source_port','destination_ip','destination_port','protocol']].drop_duplicates().shape[0]))
    pd.DataFrame(diagnostics).to_csv(out/'ip_pair_diagnostics.csv', index=False)
    print(json.dumps(diagnostics, ensure_ascii=True), flush=True)
    fingerprint = hashlib.sha256(pd.util.hash_pandas_object(data, index=True).values.tobytes()).hexdigest()
    config = dict(data_sha256=fingerprint, sklearn=sklearn.__version__, labels=labels, features=features,
                  seed=42, test_size=0.2, model={'n_estimators':100, 'class_weight':'balanced'}, groups=GROUPS)
    if (out/'config.json').exists():
        assert json.loads((out/'config.json').read_text()) == config, 'Configuration changed; use a new output directory'
    else:
        save(out/'config.json', config)
    summaries=[]
    for split in ['Random_Stratified', 'Temporal']:
        if split == 'Random_Stratified':
            train, test = train_test_split(data, test_size=.2, random_state=42, stratify=data.label)
        else:
            train, test = split_temporal_per_class(data, 'label', .2)
        assert not set(train.index) & set(test.index)
        assert set(train.label) == set(test.label) == set(labels)
        np.savez_compressed(out/f'{split}_indices.npz', train=train.index.values, test=test.index.values)
        pd.DataFrame({'train_support':train.label.value_counts(), 'test_support':test.label.value_counts()}).to_csv(out/f'{split}_support.csv')
        print(f'{split}: preprocessing {len(train)} train / {len(test)} test', flush=True)
        pre = build_preprocessor(train[features])
        xtrain = pd.DataFrame(pre.fit_transform(train[features]), columns=pre.get_feature_names_out())
        xtest = pd.DataFrame(pre.transform(test[features]), columns=pre.get_feature_names_out())
        for variant, drop in GROUPS.items():
            dest=out/f'{split}_{variant}'
            dest.mkdir(exist_ok=True)
            if (dest/'metrics.json').exists():
                metrics=json.loads((dest/'metrics.json').read_text())
            else:
                assert set(drop) <= set(xtrain.columns), f'Missing required ablation columns: {drop}'
                cols=[c for c in xtrain if c not in drop]
                reuse = split == 'Temporal' and variant == 'Full'
                if reuse:
                    model=joblib.load('models/multiclass_temporal/random_forest.joblib')
                    assert list(model.feature_names_in_) == cols
                    meta=json.loads(Path('dataset/processed_multiclass_temporal/metadata.json').read_text(encoding='utf-8'))
                    assert meta['train_rows']==len(train) and meta['test_rows']==len(test)
                    oldpre=joblib.load('dataset/processed_multiclass_temporal/preprocessor.joblib')
                    assert np.allclose(oldpre.transform(test[features]), xtest, equal_nan=True)
                else:
                    print(f'Training {split} {variant}', flush=True)
                    model=MODELS['random_forest']()
                    model.fit(xtrain[cols], train.label)
                pred=model.predict(xtest[cols])
                report=classification_report(test.label,pred,labels=labels,output_dict=True,zero_division=0)
                metrics=dict(split=split, feature_set=variant, accuracy=accuracy_score(test.label,pred),
                    macro_precision=report['macro avg']['precision'],macro_recall=report['macro avg']['recall'],
                    macro_f1=report['macro avg']['f1-score'], train_rows=len(train),test_rows=len(test),
                    reused_existing_model=reuse, dropped_columns=drop)
                if reuse:
                    old=json.loads(Path('results/multiclass_temporal/random_forest_metrics.json').read_text(encoding='utf-8'))
                    for k in ['accuracy','macro_precision','macro_recall','macro_f1']:
                        assert np.isclose(metrics[k],old[k]), f'Existing temporal result mismatch: {k}'
                pd.DataFrame({l:report[l] for l in labels}).T.rename_axis('label').to_csv(dest/'per_class.csv')
                pd.DataFrame(confusion_matrix(test.label,pred,labels=labels),index=labels,columns=labels).to_csv(dest/'confusion_matrix.csv')
                pd.DataFrame({'row_id':test.index,'label':test.label.values,'prediction':pred}).to_csv(dest/'predictions.csv',index=False)
                save(dest/'metrics.json',metrics)
                del model
                gc.collect()
            summaries.append(metrics)
            pd.DataFrame(summaries).to_csv(out/'comparison.csv',index=False)
            print(json.dumps(metrics),flush=True)
        del xtrain,xtest,train,test,pre
        gc.collect()
    print('All six experiments complete',flush=True)

if __name__=='__main__':
    main()
