"""Prediction API: is this flow an attack, which type, and how confident is the model."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, RootModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = PROJECT_ROOT / "models" / "multiclass_random" / "random_forest.joblib"
PREPROCESSOR_PATH = PROJECT_ROOT / "dataset" / "processed" / "preprocessor.joblib"
METRICS_PATH = PROJECT_ROOT / "results" / "multiclass_random" / "random_forest_metrics.json"
TEMPORAL_METRICS_PATH = (
    PROJECT_ROOT / "results" / "multiclass_temporal" / "random_forest_metrics.json"
)
CROSS_DAY_METRICS_PATH = PROJECT_ROOT / "results" / "by_day" / "random_forest_metrics.json"
RANDOM_CALIBRATION_PATH = PROJECT_ROOT / "results" / "calibration" / "multiclass_random.json"
TEMPORAL_CALIBRATION_PATH = PROJECT_ROOT / "results" / "calibration" / "multiclass_temporal.json"
CROSS_DAY_CALIBRATION_PATH = PROJECT_ROOT / "results" / "calibration" / "binary_by_day.json"
SAMPLES_PATH = PROJECT_ROOT / "api" / "sample_flows.csv"

app = FastAPI(title="AI Network Intrusion Detection API")

model = joblib.load(MODEL_PATH)
preprocessor = joblib.load(PREPROCESSOR_PATH)
metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
temporal_metrics = json.loads(TEMPORAL_METRICS_PATH.read_text(encoding="utf-8"))
cross_day_metrics = json.loads(CROSS_DAY_METRICS_PATH.read_text(encoding="utf-8"))
random_calibration = json.loads(RANDOM_CALIBRATION_PATH.read_text(encoding="utf-8"))
temporal_calibration = json.loads(TEMPORAL_CALIBRATION_PATH.read_text(encoding="utf-8"))
cross_day_calibration = json.loads(CROSS_DAY_CALIBRATION_PATH.read_text(encoding="utf-8"))
feature_names = list(preprocessor.feature_names_in_)

# Some CIC-IDS2017 labels contain a raw cp1252 en-dash byte (\x96) that
# survives cleaning as-is; normalize it for display only, not the model.
samples_df = pd.read_csv(SAMPLES_PATH)
samples_df["label"] = samples_df["label"].str.replace("\x96", "-", regex=False).str.strip()


class FlowFeatures(RootModel[dict[str, float]]):
    """A flow's raw numeric feature values, keyed by feature name."""


class PredictionResponse(BaseModel):
    is_attack: bool
    attack_type: str
    confidence: float
    low_confidence: bool
    top_predictions: list[dict[str, object]]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/model-info")
def model_info() -> dict[str, object]:
    return {
        "model_file": MODEL_PATH.name,
        "target": metrics["target"],
        "accuracy": metrics["accuracy"],
        "macro_precision": metrics["macro_precision"],
        "macro_recall": metrics["macro_recall"],
        "macro_f1": metrics["macro_f1"],
        "classes": sorted(model.classes_.tolist()),
        "feature_count": len(feature_names),
        "evaluation": {
            "random_multiclass": {
                "accuracy": metrics["accuracy"],
                "macro_f1": metrics["macro_f1"],
                "label": "隨機切分",
            },
            "temporal_multiclass": {
                "accuracy": temporal_metrics["accuracy"],
                "macro_f1": temporal_metrics["macro_f1"],
                "label": "類別內時間切分",
            },
            "cross_day_binary": {
                "accuracy": cross_day_metrics["accuracy"],
                "recall": cross_day_metrics["recall"],
                "label": "跨日期二元驗證",
            },
        },
        "calibration": {
            "random_multiclass_ece": random_calibration["expected_calibration_error"],
            "temporal_multiclass_ece": temporal_calibration["expected_calibration_error"],
            "cross_day_binary_ece": cross_day_calibration["expected_calibration_error"],
        },
        "confidence_note": (
            "隨機／類別內時間切分的 ECE 為 0.05%／1.13%，但跨日期 ECE 高達 "
            "32.97%；80% 是展示用複查門檻，不能當成部署安全保證。"
        ),
    }


@app.get("/samples")
def samples() -> list[dict[str, object]]:
    """Balanced, raw-scale test flows for honest offline replay."""
    records = []
    metadata_columns = {
        "label", "expected_prediction", "expected_confidence", "expected_correct"
    }
    for index, row in samples_df.iterrows():
        records.append({
            "id": f"flow-{index + 1:03d}",
            "label": row["label"],
            "expected_correct": bool(row.get("expected_correct", True)),
            "features": row.drop(labels=list(metadata_columns), errors="ignore").to_dict(),
        })
    return records


@app.post("/predict", response_model=PredictionResponse)
def predict(flow: FlowFeatures) -> PredictionResponse:
    values = flow.root
    missing = [name for name in feature_names if name not in values]
    unknown = [name for name in values if name not in feature_names]
    if missing or unknown:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "特徵欄位與模型不符",
                "missing_features": missing,
                "unknown_features": unknown,
            },
        )

    row = pd.DataFrame([[values[name] for name in feature_names]], columns=feature_names)
    transformed = pd.DataFrame(
        preprocessor.transform(row), columns=preprocessor.get_feature_names_out()
    )

    probabilities = model.predict_proba(transformed)[0]
    predicted_index = probabilities.argmax()
    attack_type = str(model.classes_[predicted_index])
    confidence = float(probabilities[predicted_index])
    top_indices = np.argsort(probabilities)[::-1][:3]
    top_predictions = [
        {
            "label": str(model.classes_[index]).replace("\x96", "-").strip(),
            "confidence": round(float(probabilities[index]), 4),
        }
        for index in top_indices
    ]

    return PredictionResponse(
        is_attack=attack_type.strip().upper() != "BENIGN",
        attack_type=attack_type.replace("\x96", "-").strip(),
        confidence=round(confidence, 4),
        low_confidence=confidence < 0.8,
        top_predictions=top_predictions,
    )


web_dir = PROJECT_ROOT / "web"
if web_dir.is_dir():
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
