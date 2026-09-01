"""Check whether a model's predicted probabilities are calibrated.

Confidence discrimination (mean confidence when correct vs. wrong) only shows
the model is *less sure* when it's wrong. Calibration is a stronger, separate
claim: among predictions where the model said "80% confident", are roughly
80% of them actually correct? That needs Expected Calibration Error (ECE),
Brier score, log loss, and a reliability diagram, not just a mean-confidence
comparison.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

from src.train_baseline import load_xy


def expected_calibration_error(
    confidence: np.ndarray, correct: np.ndarray, n_bins: int = 10
) -> tuple[float, list[dict]]:
    """ECE: weighted average gap between confidence and actual accuracy, per bin."""
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_index = np.clip(np.digitize(confidence, bin_edges[1:-1], right=True), 0, n_bins - 1)

    total = len(confidence)
    ece = 0.0
    bins = []
    for b in range(n_bins):
        mask = bin_index == b
        count = int(mask.sum())
        if count == 0:
            bins.append({
                "bin_range": [round(bin_edges[b], 2), round(bin_edges[b + 1], 2)],
                "count": 0, "avg_confidence": None, "accuracy": None,
            })
            continue
        avg_confidence = float(confidence[mask].mean())
        accuracy = float(correct[mask].mean())
        ece += (count / total) * abs(accuracy - avg_confidence)
        bins.append({
            "bin_range": [round(bin_edges[b], 2), round(bin_edges[b + 1], 2)],
            "count": count,
            "avg_confidence": round(avg_confidence, 4),
            "accuracy": round(accuracy, 4),
        })
    return ece, bins


def confidence_threshold_table(
    confidence: np.ndarray, correct: np.ndarray, thresholds=(0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99)
) -> list[dict]:
    """If we only auto-trust predictions >= threshold, what's covered and how accurate?"""
    total = len(confidence)
    rows = []
    for t in thresholds:
        mask = confidence >= t
        covered = int(mask.sum())
        rows.append({
            "threshold": t,
            "coverage_percent": round(covered / total * 100, 2),
            "covered_count": covered,
            "accuracy_within_covered": round(float(correct[mask].mean()), 4) if covered else None,
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="計算模型信心分數的校準指標")
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--processed-dir", type=Path, required=True)
    parser.add_argument("--target", choices=("is_attack", "label"), default="is_attack")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    model = joblib.load(args.model_path)
    x_test, y_test = load_xy(args.processed_dir / "test.csv", args.target)

    proba = model.predict_proba(x_test)
    predicted_index = proba.argmax(axis=1)
    y_pred = model.classes_[predicted_index]
    confidence = proba[np.arange(len(x_test)), predicted_index]
    correct = (np.asarray(y_test) == y_pred)

    ece, bins = expected_calibration_error(confidence, correct)
    threshold_table = confidence_threshold_table(confidence, correct)

    result: dict[str, object] = {
        "model_path": str(args.model_path),
        "target": args.target,
        "test_rows": len(x_test),
        "accuracy": float(correct.mean()),
        "expected_calibration_error": ece,
        "log_loss": float(log_loss(y_test, proba, labels=model.classes_)),
        "reliability_bins": bins,
        "confidence_threshold_table": threshold_table,
    }

    if args.target == "is_attack":
        # Brier score is defined for the binary case: squared error between
        # the predicted probability of the positive class and the true label.
        positive_index = list(model.classes_).index(1)
        p_attack = proba[:, positive_index]
        result["brier_score"] = float(brier_score_loss(y_test, p_attack))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
