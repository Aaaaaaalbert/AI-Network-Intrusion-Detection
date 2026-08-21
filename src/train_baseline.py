"""Train and evaluate a baseline Logistic Regression model on processed data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_score,
    recall_score,
)

MODELS = {
    "logistic": lambda: LogisticRegression(max_iter=1000),
    "random_forest": lambda: RandomForestClassifier(
        n_estimators=100, class_weight="balanced", n_jobs=-1, random_state=42
    ),
}


def load_xy(path: Path) -> tuple[pd.DataFrame, pd.Series]:
    frame = pd.read_csv(path)
    y = frame["is_attack"]
    # Labels and provenance are for evaluation/auditing, never model inputs.
    x = frame.drop(columns=["is_attack", "label", "source_file"], errors="ignore")
    return x, y


def main() -> None:
    parser = argparse.ArgumentParser(description="訓練基準模型")
    parser.add_argument("--processed-dir", type=Path, default=Path("dataset/processed"))
    parser.add_argument("--model-dir", type=Path, default=Path("models"))
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    parser.add_argument("--model", choices=MODELS.keys(), default="logistic")
    args = parser.parse_args()

    x_train, y_train = load_xy(args.processed_dir / "train.csv")
    x_test, y_test = load_xy(args.processed_dir / "test.csv")

    model = MODELS[args.model]()
    model.fit(x_train, y_train)

    y_pred = model.predict(x_test)
    cm = confusion_matrix(y_test, y_pred)
    metrics = {
        "model": args.model,
        "train_rows": len(x_train),
        "test_rows": len(x_test),
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred),
        "recall": recall_score(y_test, y_pred),
        "confusion_matrix": cm.tolist(),
        "majority_class_baseline_accuracy": max(y_test.value_counts()) / len(y_test),
    }

    args.model_dir.mkdir(parents=True, exist_ok=True)
    args.results_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, args.model_dir / f"{args.model}.joblib")
    (args.results_dir / f"{args.model}_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
