"""Train and evaluate a baseline Logistic Regression model on processed data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

MODELS = {
    "logistic": lambda: LogisticRegression(max_iter=1000),
    "random_forest": lambda: RandomForestClassifier(
        n_estimators=100, class_weight="balanced", n_jobs=-1, random_state=42
    ),
}


def load_xy(path: Path, target: str) -> tuple[pd.DataFrame, pd.Series]:
    frame = pd.read_csv(path)
    y = frame[target]
    # Labels and provenance are for evaluation/auditing, never model inputs.
    x = frame.drop(columns=["is_attack", "label", "source_file"], errors="ignore")
    return x, y


def predict_with_confidence(model, x: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Predict labels alongside a confidence score (probability of the predicted class)."""
    probabilities = model.predict_proba(x)
    predicted_index = probabilities.argmax(axis=1)
    predictions = model.classes_[predicted_index]
    confidence = probabilities[np.arange(len(x)), predicted_index]
    return predictions, confidence


def confidence_calibration_summary(
    y_true: pd.Series, y_pred: np.ndarray, confidence: np.ndarray
) -> dict[str, float]:
    """A well-calibrated model should be less confident when it's wrong."""
    correct = np.asarray(y_true) == y_pred
    return {
        "mean_confidence_overall": float(confidence.mean()),
        "mean_confidence_when_correct": float(confidence[correct].mean()) if correct.any() else None,
        "mean_confidence_when_wrong": float(confidence[~correct].mean()) if (~correct).any() else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="訓練基準模型")
    parser.add_argument("--processed-dir", type=Path, default=Path("dataset/processed"))
    parser.add_argument("--model-dir", type=Path, default=Path("models"))
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    parser.add_argument("--model", choices=MODELS.keys(), default="logistic")
    parser.add_argument(
        "--target",
        choices=("is_attack", "label"),
        default="is_attack",
        help="is_attack=二元判斷是否為攻擊；label=多類別判斷攻擊類型",
    )
    args = parser.parse_args()

    x_train, y_train = load_xy(args.processed_dir / "train.csv", args.target)
    x_test, y_test = load_xy(args.processed_dir / "test.csv", args.target)

    model = MODELS[args.model]()
    model.fit(x_train, y_train)

    y_pred, confidence = predict_with_confidence(model, x_test)
    calibration = confidence_calibration_summary(y_test, y_pred, confidence)

    if args.target == "is_attack":
        cm = confusion_matrix(y_test, y_pred)
        metrics = {
            "model": args.model,
            "target": args.target,
            "train_rows": len(x_train),
            "test_rows": len(x_test),
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred),
            "recall": recall_score(y_test, y_pred),
            "confusion_matrix": cm.tolist(),
            "majority_class_baseline_accuracy": max(y_test.value_counts()) / len(y_test),
            "confidence": calibration,
        }
    else:
        metrics = {
            "model": args.model,
            "target": args.target,
            "train_rows": len(x_train),
            "test_rows": len(x_test),
            "accuracy": accuracy_score(y_test, y_pred),
            "macro_precision": precision_score(y_test, y_pred, average="macro", zero_division=0),
            "macro_recall": recall_score(y_test, y_pred, average="macro", zero_division=0),
            "macro_f1": f1_score(y_test, y_pred, average="macro", zero_division=0),
            "majority_class_baseline_accuracy": max(y_test.value_counts()) / len(y_test),
            "per_class_report": classification_report(
                y_test, y_pred, output_dict=True, zero_division=0
            ),
            "confidence": calibration,
        }

    args.model_dir.mkdir(parents=True, exist_ok=True)
    args.results_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, args.model_dir / f"{args.model}.joblib")
    (args.results_dir / f"{args.model}_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Demonstrate the actual prediction output shape: label + confidence per row.
    sample = pd.DataFrame({
        "true_label": y_test.reset_index(drop=True),
        "predicted_label": y_pred,
        "confidence": confidence,
        "correct": (y_test.reset_index(drop=True) == y_pred),
    }).sample(n=min(50, len(y_test)), random_state=42).sort_index()
    sample.to_csv(args.results_dir / f"{args.model}_sample_predictions.csv", index=False)
    # ensure_ascii=True here (unlike the file write above): some CIC-IDS2017
    # labels contain non-ASCII punctuation that crashes print() on Windows
    # consoles using a limited codepage (e.g. cp950).
    print(json.dumps(metrics, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
