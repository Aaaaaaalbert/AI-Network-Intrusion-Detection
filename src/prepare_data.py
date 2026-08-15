"""Prepare tabular network-flow data for intrusion-detection models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.column_utils import clean_column_names

NORMAL_LABELS = {"0", "benign", "normal", "normal."}

# Identifier/metadata columns that are unique (or near-unique) per row.
# One-hot encoding them would explode into millions of useless columns and
# they would not generalize to traffic never seen during training anyway.
NON_FEATURE_COLUMNS = {"flow_id", "source_ip", "destination_ip", "timestamp"}


def read_csv_file(path: Path) -> pd.DataFrame:
    """Read one CSV and report its path when loading fails."""
    try:
        return pd.read_csv(path, encoding="latin1")
    except Exception as exc:
        raise ValueError(f"讀取 CSV 失敗：{path}（{exc}）") from exc


def load_csv_directory(input_dir: Path) -> pd.DataFrame:
    """Recursively load and concatenate CSV files in a stable order."""
    if not input_dir.exists():
        raise FileNotFoundError(f"輸入資料夾不存在：{input_dir}")
    if not input_dir.is_dir():
        raise NotADirectoryError(f"輸入路徑不是資料夾：{input_dir}")

    csv_files = sorted(
        (path for path in input_dir.rglob("*") if path.is_file() and path.suffix.lower() == ".csv"),
        key=lambda path: path.relative_to(input_dir).as_posix().casefold(),
    )
    if not csv_files:
        raise FileNotFoundError(f"輸入資料夾內找不到 CSV：{input_dir}")

    return pd.concat([read_csv_file(path) for path in csv_files], ignore_index=True)


def clean_data(frame: pd.DataFrame, label_column: str = "label") -> pd.DataFrame:
    """Clean a raw flow table and add binary ``is_attack`` labels."""
    data = frame.copy()
    data.columns = clean_column_names(data.columns)
    label_column = clean_column_names([label_column])[0]
    if label_column not in data.columns:
        raise ValueError(f"找不到標籤欄位：{label_column}")

    data = data.drop_duplicates().reset_index(drop=True)
    data = data.replace([np.inf, -np.inf], np.nan)
    data = data.dropna(subset=[label_column])
    labels = data[label_column].astype(str).str.strip()
    data[label_column] = labels
    data["is_attack"] = (~labels.str.lower().isin(NORMAL_LABELS)).astype("int8")
    return data


MAX_CATEGORICAL_CARDINALITY = 100


def build_preprocessor(features: pd.DataFrame) -> ColumnTransformer:
    """Build numeric and categorical transformations for a feature table."""
    numeric = features.select_dtypes(include=["number", "bool"]).columns.tolist()
    categorical = [column for column in features.columns if column not in numeric]
    if not numeric and not categorical:
        raise ValueError("資料中沒有可用的特徵欄位")

    high_cardinality = [
        column for column in categorical
        if features[column].nunique(dropna=True) > MAX_CATEGORICAL_CARDINALITY
    ]
    if high_cardinality:
        raise ValueError(
            "以下欄位類別數過多，one-hot encoding 會爆炸式增加欄位、耗盡記憶體，"
            f"請在前處理階段排除這些欄位：{high_cardinality}"
        )

    transformers = []
    if numeric:
        transformers.append(("numeric", Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]), numeric))
    if categorical:
        transformers.append(("categorical", Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]), categorical))
    return ColumnTransformer(transformers, verbose_feature_names_out=False)


def prepare_dataset(
    frame: pd.DataFrame,
    output_dir: Path,
    label_column: str = "label",
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict[str, object]:
    """Clean, split and transform data, then persist reproducible artifacts."""
    data = clean_data(frame, label_column)
    label_column = clean_column_names([label_column])[0]
    excluded_columns = {label_column, "is_attack"} | NON_FEATURE_COLUMNS
    feature_columns = [c for c in data.columns if c not in excluded_columns]
    if not feature_columns:
        raise ValueError("移除標籤後沒有可用的特徵")
    if data["is_attack"].nunique() < 2:
        raise ValueError("資料必須同時包含正常與攻擊流量")

    train, test = train_test_split(
        data,
        test_size=test_size,
        random_state=random_state,
        stratify=data["is_attack"],
    )
    preprocessor = build_preprocessor(train[feature_columns])
    train_values = preprocessor.fit_transform(train[feature_columns])
    test_values = preprocessor.transform(test[feature_columns])
    transformed_columns = preprocessor.get_feature_names_out().tolist()

    train_output = pd.DataFrame(train_values, columns=transformed_columns)
    train_output[[label_column, "is_attack"]] = train[[label_column, "is_attack"]].reset_index(drop=True)
    test_output = pd.DataFrame(test_values, columns=transformed_columns)
    test_output[[label_column, "is_attack"]] = test[[label_column, "is_attack"]].reset_index(drop=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    train_output.to_csv(output_dir / "train.csv", index=False)
    test_output.to_csv(output_dir / "test.csv", index=False)
    joblib.dump(preprocessor, output_dir / "preprocessor.joblib")

    metadata: dict[str, object] = {
        "rows_after_cleaning": len(data),
        "train_rows": len(train),
        "test_rows": len(test),
        "raw_feature_columns": feature_columns,
        "transformed_feature_columns": transformed_columns,
        "label_column": label_column,
        "class_distribution": {
            str(key): int(value) for key, value in data[label_column].value_counts().items()
        },
        "random_state": random_state,
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return metadata


def demo_data(rows: int = 200, random_state: int = 42) -> pd.DataFrame:
    """Create a small deterministic dataset for checking the pipeline."""
    rng = np.random.default_rng(random_state)
    attack = rng.random(rows) < 0.3
    return pd.DataFrame({
        "Duration": rng.exponential(np.where(attack, 5.0, 1.5)),
        "Protocol": rng.choice(["TCP", "UDP", "ICMP"], rows),
        "Source Bytes": rng.integers(40, 1500, rows) + attack * rng.integers(0, 5000, rows),
        "Destination Bytes": rng.integers(40, 2000, rows),
        "Packet Count": rng.integers(1, 80, rows) + attack * rng.integers(0, 200, rows),
        "Label": np.where(attack, rng.choice(["DoS", "PortScan", "BruteForce"], rows), "BENIGN"),
    })


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description="準備網路入侵偵測資料")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="原始 CSV 路徑")
    source.add_argument("--input-dir", type=Path, help="遞迴讀取資料夾內所有 CSV")
    source.add_argument("--demo", action="store_true", help="使用內建示範資料")
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--label-column", default="label")
    parser.add_argument("--test-size", type=float, default=0.2)
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.demo:
        frame = demo_data()
    elif args.input_dir is not None:
        frame = load_csv_directory(args.input_dir)
    else:
        frame = read_csv_file(args.input)
    metadata = prepare_dataset(frame, args.output_dir, args.label_column, args.test_size)
    print(f"完成：{metadata['train_rows']} 筆訓練資料、{metadata['test_rows']} 筆測試資料")
    print(f"輸出位置：{args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
