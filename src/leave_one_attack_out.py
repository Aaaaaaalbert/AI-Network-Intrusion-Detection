"""Audit how the classifiers behave when one attack type is unseen in training.

This is not an open-set detector: the multiclass model has no UNKNOWN output.
The experiment measures whether the binary model still recognises an unseen
attack as malicious, and which known label the closed-set multiclass model
forces that attack into.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler


NON_FEATURE_COLUMNS = {"label", "is_attack", "source_file", "__priority"}


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Return a 95% Wilson confidence interval for a binomial proportion."""
    if total == 0:
        return (math.nan, math.nan)
    proportion = successes / total
    denominator = 1 + z**2 / total
    centre = proportion + z**2 / (2 * total)
    margin = z * math.sqrt(
        proportion * (1 - proportion) / total + z**2 / (4 * total**2)
    )
    return ((centre - margin) / denominator, (centre + margin) / denominator)


def _retain_smallest_priorities(
    existing: pd.DataFrame | None, incoming: pd.DataFrame, limit: int
) -> pd.DataFrame:
    combined = incoming if existing is None else pd.concat([existing, incoming], ignore_index=True)
    if len(combined) > limit:
        combined = combined.nsmallest(limit, "__priority")
    return combined.reset_index(drop=True)


def reservoir_sample_by_label(
    csv_paths: list[Path],
    per_label_limit: int,
    benign_limit: int,
    random_state: int,
    chunksize: int = 50_000,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Read large processed CSVs in chunks and retain a random sample per label."""
    rng = np.random.default_rng(random_state)
    reservoirs: dict[str, pd.DataFrame] = {}
    counts: Counter[str] = Counter()

    for path in csv_paths:
        if not path.exists():
            raise FileNotFoundError(f"找不到處理後資料：{path}")
        for chunk in pd.read_csv(path, chunksize=chunksize):
            required = {"label", "is_attack"}
            missing = required - set(chunk.columns)
            if missing:
                raise ValueError(f"{path} 缺少必要欄位：{sorted(missing)}")
            chunk["__priority"] = rng.random(len(chunk))
            for label, group in chunk.groupby("label", sort=False):
                label = str(label)
                counts[label] += len(group)
                is_benign = bool((group["is_attack"] == 0).all())
                limit = benign_limit if is_benign else per_label_limit
                reservoirs[label] = _retain_smallest_priorities(
                    reservoirs.get(label), group, limit
                )

    if not reservoirs:
        raise ValueError("處理後資料沒有任何資料列")
    sampled = pd.concat(reservoirs.values(), ignore_index=True)
    return sampled, dict(counts)


def split_benign_pool(
    sampled: pd.DataFrame,
    benign_test_size: int,
    max_train_per_class: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    benign = sampled.loc[sampled["is_attack"] == 0].sort_values("__priority")
    if len(benign) <= benign_test_size:
        raise ValueError(
            f"正常流量樣本只有 {len(benign)} 筆，必須多於測試需求 {benign_test_size} 筆"
        )
    benign_test = benign.iloc[:benign_test_size].copy()
    benign_train = benign.iloc[benign_test_size:benign_test_size + max_train_per_class].copy()
    return benign_train, benign_test


def training_frame_for_attack(
    sampled: pd.DataFrame,
    benign_train: pd.DataFrame,
    held_out_attack: str,
    max_train_per_class: int,
) -> pd.DataFrame:
    attack_parts = []
    attacks = sampled.loc[sampled["is_attack"] == 1]
    for label, group in attacks.groupby("label", sort=True):
        if str(label) == held_out_attack:
            continue
        attack_parts.append(
            group.nsmallest(min(len(group), max_train_per_class), "__priority")
        )
    if not attack_parts:
        raise ValueError("移除目標攻擊後沒有其他攻擊類型可供訓練")
    return pd.concat([benign_train, *attack_parts], ignore_index=True)


def _predict_with_confidence(model, features: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    probabilities = model.predict_proba(features)
    indices = probabilities.argmax(axis=1)
    predictions = model.classes_[indices]
    confidence = probabilities[np.arange(len(features)), indices]
    return predictions, confidence, probabilities


def binary_metrics(
    attack_predictions: np.ndarray,
    attack_confidence: np.ndarray,
    attack_probability: np.ndarray,
    benign_predictions: np.ndarray,
    confidence_threshold: float,
) -> dict[str, object]:
    detected = int(np.sum(attack_predictions == 1))
    total_attack = len(attack_predictions)
    benign_correct = int(np.sum(benign_predictions == 0))
    ci_low, ci_high = wilson_interval(detected, total_attack)
    false_negative_mask = attack_predictions == 0
    return {
        "unseen_attack_recall": detected / total_attack,
        "unseen_attack_recall_ci95": [ci_low, ci_high],
        "unseen_attack_false_negatives": int(false_negative_mask.sum()),
        "benign_specificity": benign_correct / len(benign_predictions),
        "benign_false_positive_rate": 1 - benign_correct / len(benign_predictions),
        "mean_attack_probability": float(attack_probability.mean()),
        "mean_predicted_confidence_on_attack": float(attack_confidence.mean()),
        "high_confidence_false_negative_rate": float(
            np.mean(false_negative_mask & (attack_confidence >= confidence_threshold))
        ),
    }


def multiclass_metrics(
    predictions: np.ndarray,
    confidence: np.ndarray,
    normal_label: str,
    confidence_threshold: float,
) -> dict[str, object]:
    predicted_benign = predictions == normal_label
    counts = pd.Series(predictions).value_counts()
    return {
        "predicted_as_attack_rate": float(np.mean(~predicted_benign)),
        "predicted_as_benign_rate": float(np.mean(predicted_benign)),
        "mean_predicted_confidence": float(confidence.mean()),
        "high_confidence_benign_rate": float(
            np.mean(predicted_benign & (confidence >= confidence_threshold))
        ),
        "most_common_forced_label": str(counts.index[0]),
        "prediction_distribution": {
            str(label): int(count) for label, count in counts.items()
        },
    }


def run_one_attack(
    training_sample: pd.DataFrame,
    evaluation_sample: pd.DataFrame,
    benign_train: pd.DataFrame,
    benign_test: pd.DataFrame,
    held_out_attack: str,
    max_train_per_class: int,
    max_holdout_per_attack: int,
    confidence_threshold: float,
    model_factory: Callable[[], RandomForestClassifier],
) -> tuple[dict[str, object], pd.DataFrame]:
    """Train binary and multiclass models without one label and audit predictions."""
    training = training_frame_for_attack(
        training_sample, benign_train, held_out_attack, max_train_per_class
    )
    holdout = (
        evaluation_sample.loc[evaluation_sample["label"] == held_out_attack]
        .nsmallest(max_holdout_per_attack, "__priority")
        .copy()
    )
    if holdout.empty:
        raise ValueError(f"找不到留出攻擊類型：{held_out_attack}")

    feature_columns = [
        column for column in training_sample.columns if column not in NON_FEATURE_COLUMNS
    ]
    scaler = StandardScaler()
    x_train = scaler.fit_transform(training[feature_columns])
    x_attack = scaler.transform(holdout[feature_columns])
    x_benign = scaler.transform(benign_test[feature_columns])

    binary_model = model_factory()
    binary_model.fit(x_train, training["is_attack"])
    attack_binary_pred, attack_binary_conf, attack_binary_proba = _predict_with_confidence(
        binary_model, x_attack
    )
    benign_binary_pred, _, _ = _predict_with_confidence(binary_model, x_benign)
    attack_class_index = int(np.flatnonzero(binary_model.classes_ == 1)[0])

    multiclass_model = model_factory()
    multiclass_model.fit(x_train, training["label"])
    multiclass_pred, multiclass_conf, _ = _predict_with_confidence(
        multiclass_model, x_attack
    )
    normal_labels = training.loc[training["is_attack"] == 0, "label"].value_counts()
    normal_label = str(normal_labels.index[0])

    result = {
        "held_out_attack": held_out_attack,
        "full_dataset_samples": int(
            (training_sample["label"] == held_out_attack).sum()
            + (evaluation_sample["label"] == held_out_attack).sum()
        ),
        "holdout_test_rows": len(holdout),
        "training_rows": len(training),
        "training_labels": sorted(str(label) for label in training["label"].unique()),
        "source_files": {
            str(name): int(count)
            for name, count in holdout.get("source_file", pd.Series(dtype=str)).value_counts().items()
        },
        "binary": binary_metrics(
            attack_binary_pred,
            attack_binary_conf,
            attack_binary_proba[:, attack_class_index],
            benign_binary_pred,
            confidence_threshold,
        ),
        "multiclass": multiclass_metrics(
            multiclass_pred, multiclass_conf, normal_label, confidence_threshold
        ),
    }

    prediction_sample = pd.DataFrame({
        "held_out_attack": held_out_attack,
        "source_file": holdout.get("source_file", pd.Series([""] * len(holdout))).to_numpy(),
        "binary_prediction": attack_binary_pred,
        "binary_confidence": attack_binary_conf,
        "binary_attack_probability": attack_binary_proba[:, attack_class_index],
        "multiclass_prediction": multiclass_pred,
        "multiclass_confidence": multiclass_conf,
    })
    return result, prediction_sample.sample(
        n=min(100, len(prediction_sample)), random_state=42
    ).sort_index()


def fit_seen_control(
    training_sample: pd.DataFrame,
    benign_train: pd.DataFrame,
    max_train_per_class: int,
    model_factory: Callable[[], RandomForestClassifier],
) -> tuple[StandardScaler, RandomForestClassifier, RandomForestClassifier, list[str]]:
    """Fit matched models that have seen every attack using the same sample caps."""
    control_training = training_frame_for_attack(
        training_sample,
        benign_train,
        held_out_attack="__no_label_is_held_out__",
        max_train_per_class=max_train_per_class,
    )
    feature_columns = [
        column for column in training_sample.columns if column not in NON_FEATURE_COLUMNS
    ]
    scaler = StandardScaler()
    x_train = scaler.fit_transform(control_training[feature_columns])
    binary_model = model_factory()
    binary_model.fit(x_train, control_training["is_attack"])
    multiclass_model = model_factory()
    multiclass_model.fit(x_train, control_training["label"])
    return scaler, binary_model, multiclass_model, feature_columns


def evaluate_seen_control(
    scaler: StandardScaler,
    binary_model: RandomForestClassifier,
    multiclass_model: RandomForestClassifier,
    feature_columns: list[str],
    evaluation_sample: pd.DataFrame,
    benign_test: pd.DataFrame,
    held_out_attack: str,
    max_holdout_per_attack: int,
    confidence_threshold: float,
) -> dict[str, object]:
    """Evaluate the matched seen-class control on the same held-out rows."""
    holdout = (
        evaluation_sample.loc[evaluation_sample["label"] == held_out_attack]
        .nsmallest(max_holdout_per_attack, "__priority")
        .copy()
    )
    x_attack = scaler.transform(holdout[feature_columns])
    x_benign = scaler.transform(benign_test[feature_columns])
    binary_pred, binary_conf, binary_proba = _predict_with_confidence(
        binary_model, x_attack
    )
    benign_pred, _, _ = _predict_with_confidence(binary_model, x_benign)
    attack_class_index = int(np.flatnonzero(binary_model.classes_ == 1)[0])
    binary = binary_metrics(
        binary_pred,
        binary_conf,
        binary_proba[:, attack_class_index],
        benign_pred,
        confidence_threshold,
    )
    multiclass_pred, multiclass_conf, _ = _predict_with_confidence(
        multiclass_model, x_attack
    )
    return {
        "binary": binary,
        "multiclass_correct_recall": float(np.mean(multiclass_pred == held_out_attack)),
        "multiclass_mean_confidence": float(multiclass_conf.mean()),
    }


def _percentage(value: float) -> str:
    return f"{value * 100:.2f}%"


def _display_label(value: object) -> str:
    """Replace CIC-IDS2017's latin1 control character with a readable dash."""
    return str(value).replace("\x96", "–")


def write_report(
    results: list[dict[str, object]],
    class_counts: dict[str, int],
    excluded_labels: list[str],
    output_path: Path,
    config: dict[str, object],
) -> None:
    lines = [
        "# 留一攻擊類型泛化測試",
        "",
        "本實驗每次將一種攻擊類型完全移出分類器訓練，再觀察二元模型能否仍將其辨識為攻擊，以及封閉式多類別模型會把它歸到哪個已知類別。另以相同抽樣上限、模型參數與測試資料建立『看過該攻擊』的 matched control，避免把訓練規模差異誤認成未知攻擊造成的退步。這不是完整的未知攻擊偵測器，因為模型沒有 `UNKNOWN` 輸出。",
        "",
        "## 結果",
        "",
        "| 留出攻擊 | 原始樣本數 | 測試筆數 | 看過時 Recall | 未見時 Recall | 下降 | 未見時高信心漏報 | 正常誤報率 | 多類別看過時正確率 | 未見時判成 BENIGN | 最常被迫歸類為 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for result in results:
        binary = result["binary"]
        multiclass = result["multiclass"]
        control = result["seen_control"]
        recall_drop = control["binary"]["unseen_attack_recall"] - binary["unseen_attack_recall"]
        lines.append(
            "| {label} | {count:,} | {test:,} | {seen_recall} | {recall} | {drop} | {high_fn} | {benign_fpr} | {seen_multi} | {benign} | {forced} |".format(
                label=_display_label(result["held_out_attack"]),
                count=class_counts[result["held_out_attack"]],
                test=result["holdout_test_rows"],
                seen_recall=_percentage(control["binary"]["unseen_attack_recall"]),
                recall=_percentage(binary["unseen_attack_recall"]),
                drop=_percentage(recall_drop),
                high_fn=_percentage(binary["high_confidence_false_negative_rate"]),
                benign_fpr=_percentage(binary["benign_false_positive_rate"]),
                seen_multi=_percentage(control["multiclass_correct_recall"]),
                benign=_percentage(multiclass["predicted_as_benign_rate"]),
                forced=_display_label(multiclass["most_common_forced_label"]),
            )
        )

    recalls = np.array([result["binary"]["unseen_attack_recall"] for result in results])
    test_rows = np.array([result["holdout_test_rows"] for result in results])
    weighted_recall = float(np.average(recalls, weights=test_rows))
    seen_recalls = np.array([
        result["seen_control"]["binary"]["unseen_attack_recall"] for result in results
    ])
    recall_drops = seen_recalls - recalls
    weakest = sorted(results, key=lambda item: item["binary"]["unseen_attack_recall"])[:3]
    strongest = sorted(
        results, key=lambda item: item["binary"]["unseen_attack_recall"], reverse=True
    )[:3]
    high_confidence_misses = sorted(
        results,
        key=lambda item: item["binary"]["high_confidence_false_negative_rate"],
        reverse=True,
    )[:3]
    forced_attack_labels = [
        result for result in results
        if result["multiclass"]["most_common_forced_label"] != "BENIGN"
    ]
    lines.extend([
        "",
        "## 主要發現",
        "",
        f"- 在完全相同的抽樣與模型設定下，11 類攻擊『看過時』的二元 Recall 等權平均為 **{_percentage(float(seen_recalls.mean()))}**，移除該類後降為 **{_percentage(float(recalls.mean()))}**，平均下降 **{_percentage(float(recall_drops.mean()))}**。未見攻擊 Recall 的中位數為 **{_percentage(float(np.median(recalls)))}**，依本次測試筆數加權後為 **{_percentage(weighted_recall)}**。",
        "- 最弱的三類是 " + "、".join(
            f"`{_display_label(item['held_out_attack'])}`（{_percentage(item['binary']['unseen_attack_recall'])}）"
            for item in weakest
        ) + "。",
        "- 最能從其他攻擊特徵泛化的三類是 " + "、".join(
            f"`{_display_label(item['held_out_attack'])}`（{_percentage(item['binary']['unseen_attack_recall'])}）"
            for item in strongest
        ) + "。",
        "- 高信心漏報最嚴重的是 " + "、".join(
            f"`{_display_label(item['held_out_attack'])}`（{_percentage(item['binary']['high_confidence_false_negative_rate'])}）"
            for item in high_confidence_misses
        ) + f"；此處『高信心漏報』指全部留出攻擊中，被判為 BENIGN 且預測信心至少 {config['confidence_threshold']:.0%} 的比例。",
        "- 各次實驗的正常流量誤報率約落在 **{low}–{high}**，表示上述 Recall 差異不是靠大幅提高正常流量誤報換來的。".format(
            low=_percentage(min(item["binary"]["benign_false_positive_rate"] for item in results)),
            high=_percentage(max(item["binary"]["benign_false_positive_rate"] for item in results)),
        ),
    ])
    if forced_attack_labels:
        lines.append(
            "- 多類別模型有時會將未見攻擊歸入另一個已知攻擊，其中部分同屬相近家族：" + "；".join(
                f"`{_display_label(item['held_out_attack'])}` → `{_display_label(item['multiclass']['most_common_forced_label'])}`"
                for item in forced_attack_labels
            ) + "。其餘類型最常被迫歸為 BENIGN。"
        )

    lines.extend([
        "",
        "## 實驗限制",
        "",
        "- CIC-IDS2017 的每種攻擊只出現在單一日期，因此攻擊型態與日期／場景仍然糾纏；本實驗不能單獨估計純粹的跨日期漂移。",
        "- 多類別模型沒有 `UNKNOWN` 類別，所以此處衡量的是強制錯分行為，不是宣稱已能識別未知攻擊。",
        "- 為控制訓練時間，各類別使用可重現的上限抽樣；matched control 與留一類模型使用相同上限、模型參數和測試資料，因此適合比較『看過 vs 未見』的差值，但原始樣本數仍列在表中，絕對分數只代表這次設定。",
        "- 輸入來自既有清理後數值資料，並在每次實驗中以該次訓練樣本重新 fit 標準化器；留出攻擊不參與分類器與這次標準化器的 fit。",
        "- 95% Wilson 區間把每列流量視為獨立二項試驗；同一攻擊場景的流量實際高度相關，因此區間可能偏窄，只作逐列描述，不代表跨場景的不確定性。",
        "- 樣本極少的類別不納入主要比較，不能將不足樣本解讀為模型已經或尚未學會該攻擊。",
        "",
        "## 未納入主要比較的少數類別",
        "",
    ])
    if excluded_labels:
        for label in excluded_labels:
            lines.append(f"- `{_display_label(label)}`：{class_counts[label]:,} 筆")
    else:
        lines.append("- 無")
    lines.extend([
        "",
        "## 執行設定",
        "",
        "```json",
        json.dumps(config, ensure_ascii=False, indent=2),
        "```",
        "",
    ])
    output_path.write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="留一攻擊類型泛化測試")
    parser.add_argument(
        "--processed-dir", type=Path, default=Path("dataset/processed")
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("results/leave_one_attack_out")
    )
    parser.add_argument("--min-attack-samples", type=int, default=500)
    parser.add_argument("--max-train-per-class", type=int, default=20_000)
    parser.add_argument("--max-holdout-per-attack", type=int, default=20_000)
    parser.add_argument("--benign-test-size", type=int, default=20_000)
    parser.add_argument("--n-estimators", type=int, default=50)
    parser.add_argument("--confidence-threshold", type=float, default=0.8)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--chunksize", type=int, default=50_000)
    parser.add_argument(
        "--attacks",
        nargs="*",
        help="只測指定攻擊類型；省略時測所有達到最少樣本門檻的類型",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    training_sample, train_counts = reservoir_sample_by_label(
        [args.processed_dir / "train.csv"],
        per_label_limit=args.max_train_per_class,
        benign_limit=args.max_train_per_class,
        random_state=args.random_state,
        chunksize=args.chunksize,
    )
    evaluation_sample, test_counts = reservoir_sample_by_label(
        [args.processed_dir / "test.csv"],
        per_label_limit=args.max_holdout_per_attack,
        benign_limit=args.benign_test_size,
        random_state=args.random_state + 1,
        chunksize=args.chunksize,
    )
    class_counts = {
        label: train_counts.get(label, 0) + test_counts.get(label, 0)
        for label in set(train_counts) | set(test_counts)
    }
    benign_train = training_sample.loc[training_sample["is_attack"] == 0].copy()
    benign_test = evaluation_sample.loc[evaluation_sample["is_attack"] == 0].copy()
    if benign_train.empty or benign_test.empty:
        raise ValueError("訓練與測試資料都必須包含正常流量")

    attack_labels = {
        label
        for label in class_counts
        if label in set(training_sample.loc[training_sample["is_attack"] == 1, "label"])
        and label in set(evaluation_sample.loc[evaluation_sample["is_attack"] == 1, "label"])
    }
    all_attacks = sorted(
        label for label in attack_labels if class_counts[label] >= args.min_attack_samples
    )
    selected_attacks = args.attacks or all_attacks
    unknown = sorted(set(selected_attacks) - set(class_counts))
    if unknown:
        raise ValueError(f"指定了不存在的攻擊類型：{unknown}")
    non_attacks = sorted(set(selected_attacks) - attack_labels)
    if non_attacks:
        raise ValueError(f"指定標籤不是攻擊類型：{non_attacks}")
    too_small = [
        label for label in selected_attacks if class_counts[label] < args.min_attack_samples
    ]
    if too_small:
        raise ValueError(
            f"指定攻擊低於 --min-attack-samples={args.min_attack_samples}：{too_small}"
        )

    def model_factory() -> RandomForestClassifier:
        return RandomForestClassifier(
            n_estimators=args.n_estimators,
            class_weight="balanced",
            n_jobs=-1,
            random_state=args.random_state,
        )

    print("建立相同設定的看過類別控制組", flush=True)
    control_scaler, control_binary, control_multiclass, feature_columns = fit_seen_control(
        training_sample,
        benign_train,
        args.max_train_per_class,
        model_factory,
    )

    results: list[dict[str, object]] = []
    prediction_samples = []
    for index, attack in enumerate(selected_attacks, start=1):
        print(f"[{index}/{len(selected_attacks)}] 留出 {attack}", flush=True)
        result, sample = run_one_attack(
            training_sample,
            evaluation_sample,
            benign_train,
            benign_test,
            attack,
            args.max_train_per_class,
            args.max_holdout_per_attack,
            args.confidence_threshold,
            model_factory,
        )
        result["seen_control"] = evaluate_seen_control(
            control_scaler,
            control_binary,
            control_multiclass,
            feature_columns,
            evaluation_sample,
            benign_test,
            attack,
            args.max_holdout_per_attack,
            args.confidence_threshold,
        )
        result["full_dataset_samples"] = class_counts[attack]
        results.append(result)
        prediction_samples.append(sample)

    excluded_labels = sorted(
        label
        for label, count in class_counts.items()
        if label not in all_attacks
        and (
            label in set(training_sample.loc[training_sample["is_attack"] == 1, "label"])
            or label in set(evaluation_sample.loc[evaluation_sample["is_attack"] == 1, "label"])
        )
    )
    config = {
        "processed_dir": str(args.processed_dir),
        "random_state": args.random_state,
        "min_attack_samples": args.min_attack_samples,
        "max_train_per_class": args.max_train_per_class,
        "max_holdout_per_attack": args.max_holdout_per_attack,
        "benign_test_size": args.benign_test_size,
        "n_estimators": args.n_estimators,
        "confidence_threshold": args.confidence_threshold,
        "matched_control": True,
        "selected_attacks": selected_attacks,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "experiment": "leave_one_attack_type_out",
        "interpretation": "generalization audit, not an UNKNOWN-class detector",
        "config": config,
        "class_counts": class_counts,
        "excluded_low_sample_attacks": excluded_labels,
        "results": results,
    }
    (args.output_dir / "results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary_rows = []
    for result in results:
        binary = result["binary"]
        multiclass = result["multiclass"]
        control = result["seen_control"]
        summary_rows.append({
            "held_out_attack": result["held_out_attack"],
            "full_dataset_samples": class_counts[result["held_out_attack"]],
            "holdout_test_rows": result["holdout_test_rows"],
            "control_seen_binary_recall": control["binary"]["unseen_attack_recall"],
            "binary_unseen_attack_recall": binary["unseen_attack_recall"],
            "binary_recall_drop_when_unseen": (
                control["binary"]["unseen_attack_recall"]
                - binary["unseen_attack_recall"]
            ),
            "binary_recall_ci95_low": binary["unseen_attack_recall_ci95"][0],
            "binary_recall_ci95_high": binary["unseen_attack_recall_ci95"][1],
            "binary_high_confidence_false_negative_rate": binary["high_confidence_false_negative_rate"],
            "binary_benign_false_positive_rate": binary["benign_false_positive_rate"],
            "control_seen_multiclass_recall": control["multiclass_correct_recall"],
            "multiclass_predicted_as_benign_rate": multiclass["predicted_as_benign_rate"],
            "multiclass_most_common_forced_label": multiclass["most_common_forced_label"],
            "multiclass_mean_confidence": multiclass["mean_predicted_confidence"],
        })
    pd.DataFrame(summary_rows).to_csv(args.output_dir / "summary.csv", index=False)
    pd.concat(prediction_samples, ignore_index=True).to_csv(
        args.output_dir / "sample_predictions.csv", index=False
    )
    write_report(
        results,
        class_counts,
        excluded_labels,
        args.output_dir / "report.md",
        config,
    )
    print(f"完成：{args.output_dir / 'report.md'}", flush=True)


if __name__ == "__main__":
    main()
