"""Build balanced, raw-scale replay samples from the processed test set."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description="建立 API／網頁使用的真實流量重播樣本")
    parser.add_argument("--processed-dir", type=Path, default=Path("dataset/processed"))
    parser.add_argument(
        "--model", type=Path, default=Path("models/multiclass_random/random_forest.joblib")
    )
    parser.add_argument("--output", type=Path, default=Path("api/sample_flows.csv"))
    parser.add_argument("--correct-per-class", type=int, default=5)
    parser.add_argument("--wrong-per-class", type=int, default=2)
    args = parser.parse_args()

    preprocessor = joblib.load(args.processed_dir / "preprocessor.joblib")
    model = joblib.load(args.model)
    raw_features = list(preprocessor.feature_names_in_)
    transformed_features = list(preprocessor.get_feature_names_out())
    numeric_pipeline = preprocessor.named_transformers_["numeric"]
    scaler = numeric_pipeline.named_steps["scaler"]

    picked: defaultdict[str, dict[str, list[pd.Series]]] = defaultdict(
        lambda: {"correct": [], "wrong": []}
    )

    for chunk in pd.read_csv(args.processed_dir / "test.csv", chunksize=100_000):
        predictions = model.predict(chunk[transformed_features])
        probabilities = model.predict_proba(chunk[transformed_features])
        confidence = probabilities.max(axis=1)

        for position, (_, row) in enumerate(chunk.iterrows()):
            label = str(row["label"])
            kind = "correct" if predictions[position] == label else "wrong"
            limit = args.correct_per_class if kind == "correct" else args.wrong_per_class
            if len(picked[label][kind]) >= limit:
                continue
            selected = row[transformed_features].copy()
            selected["label"] = label
            selected["expected_prediction"] = str(predictions[position])
            selected["expected_confidence"] = float(confidence[position])
            selected["expected_correct"] = kind == "correct"
            picked[label][kind].append(selected)

    selected_rows = []
    for label in sorted(picked):
        selected_rows.extend(picked[label]["wrong"])
        selected_rows.extend(picked[label]["correct"])
    if not selected_rows:
        raise ValueError("測試集中找不到可用的重播樣本")

    selected = pd.DataFrame(selected_rows).reset_index(drop=True)
    raw_values = scaler.inverse_transform(selected[transformed_features])
    raw = pd.DataFrame(raw_values, columns=raw_features)
    output = pd.concat(
        [
            selected[[
                "label", "expected_prediction", "expected_confidence", "expected_correct"
            ]],
            raw,
        ],
        axis=1,
    )

    # Remove tiny floating-point inverse-transform residue from integer-like zeros.
    numeric_columns = output.select_dtypes(include=[np.number]).columns
    output[numeric_columns] = output[numeric_columns].mask(
        output[numeric_columns].abs() < 1e-10, 0.0
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False, float_format="%.12g")
    print(f"建立 {len(output)} 筆重播樣本：{args.output}")


if __name__ == "__main__":
    main()
