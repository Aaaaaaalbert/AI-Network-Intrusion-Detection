"""Analyze binary-model misses by original attack label and source file."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import joblib
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description="依攻擊類型與來源檔分析二元模型錯誤")
    parser.add_argument("--test-csv", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--chunk-size", type=int, default=100_000)
    args = parser.parse_args()

    model = joblib.load(args.model)
    totals: defaultdict[str, int] = defaultdict(int)
    misses: defaultdict[str, int] = defaultdict(int)
    by_source: defaultdict[str, dict[str, int]] = defaultdict(
        lambda: {"total_attacks": 0, "missed_attacks": 0}
    )

    for frame in pd.read_csv(args.test_csv, chunksize=args.chunk_size):
        feature_columns = [
            column for column in frame.columns
            if column not in {"label", "is_attack", "source_file"}
        ]
        predictions = model.predict(frame[feature_columns])
        attack_mask = frame["is_attack"].eq(1)
        missed_mask = attack_mask & (predictions == 0)

        for label, count in frame.loc[attack_mask, "label"].value_counts().items():
            totals[str(label)] += int(count)
        for label, count in frame.loc[missed_mask, "label"].value_counts().items():
            misses[str(label)] += int(count)

        if "source_file" in frame.columns:
            for source, group in frame.groupby("source_file"):
                group_attack = group["is_attack"].eq(1)
                group_predictions = predictions[group.index.to_numpy() - frame.index[0]]
                by_source[str(source)]["total_attacks"] += int(group_attack.sum())
                by_source[str(source)]["missed_attacks"] += int(
                    (group_attack.to_numpy() & (group_predictions == 0)).sum()
                )

    by_attack_type = {}
    for label in sorted(totals):
        total = totals[label]
        missed = misses[label]
        by_attack_type[label] = {
            "missed": missed,
            "total": total,
            "miss_rate_percent": round(100 * missed / total, 2),
            "recall_percent": round(100 * (total - missed) / total, 2),
        }

    for values in by_source.values():
        total = values["total_attacks"]
        missed = values["missed_attacks"]
        values["miss_rate_percent"] = round(100 * missed / total, 2) if total else None
        values["recall_percent"] = round(100 * (total - missed) / total, 2) if total else None

    result = {
        "by_attack_type": by_attack_type,
        "by_source_file": dict(sorted(by_source.items())),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
