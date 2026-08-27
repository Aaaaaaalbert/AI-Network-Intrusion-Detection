import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.prepare_data import (
    build_parser,
    clean_data,
    demo_data,
    load_csv_directory,
    prepare_dataset,
    read_csv_file,
)


class PrepareDataTests(unittest.TestCase):
    def test_load_csv_directory_combines_csv_files_recursively_in_stable_order(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory)
            (raw / "nested").mkdir()
            pd.DataFrame({"value": [2]}).to_csv(raw / "b.csv", index=False)
            pd.DataFrame({"value": [1]}).to_csv(raw / "A.CSV", index=False)
            pd.DataFrame({"value": [3]}).to_csv(raw / "nested" / "c.csv", index=False)

            combined = load_csv_directory(raw)

            self.assertEqual(combined["value"].tolist(), [1, 2, 3])
            self.assertEqual(
                combined["source_file"].tolist(),
                ["A.CSV", "b.csv", "nested/c.csv"],
            )

    def test_load_csv_directory_rejects_empty_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(FileNotFoundError, "找不到 CSV"):
                load_csv_directory(Path(directory))

    def test_single_input_reader_preserves_existing_behavior(self):
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "single.csv"
            expected = pd.DataFrame({"feature": [1, 2], "Label": ["BENIGN", "DoS"]})
            expected.to_csv(csv_path, index=False)

            pd.testing.assert_frame_equal(read_csv_file(csv_path), expected)

    def test_cli_sources_are_required_and_mutually_exclusive(self):
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args([])
        with self.assertRaises(SystemExit):
            parser.parse_args(["--input", "one.csv", "--input-dir", "raw"])
        with self.assertRaises(SystemExit):
            parser.parse_args(["--input-dir", "raw", "--demo"])
        self.assertEqual(parser.parse_args(["--input-dir", "raw"]).input_dir, Path("raw"))

    def test_clean_data_normalizes_columns_labels_and_duplicates(self):
        raw = pd.DataFrame({
            " Flow Duration ": [1.0, 1.0, 2.0],
            "Label": [" BENIGN ", " BENIGN ", "DoS"],
        })
        cleaned = clean_data(raw)
        self.assertEqual(list(cleaned.columns), ["flow_duration", "label", "is_attack"])
        self.assertEqual(cleaned["is_attack"].tolist(), [0, 1])

    def test_prepare_dataset_writes_all_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            metadata = prepare_dataset(demo_data(100), output)
            self.assertEqual(metadata["train_rows"], 80)
            self.assertEqual(metadata["test_rows"], 20)
            for name in ("train.csv", "test.csv", "preprocessor.joblib", "metadata.json"):
                self.assertTrue((output / name).exists(), name)
            train = pd.read_csv(output / "train.csv")
            self.assertIn("is_attack", train.columns)
            self.assertFalse(train.isna().any().any())

    def test_prepare_dataset_can_hold_out_files_by_prefix(self):
        frame = pd.DataFrame({
            "feature": [1, 2, 3, 4, 5, 6],
            "Label": ["BENIGN", "DoS", "BENIGN", "DoS", "BENIGN", "PortScan"],
            "source_file": [
                "Monday.csv", "Monday.csv", "Tuesday.csv", "Tuesday.csv",
                "Friday-Morning.csv", "Friday-Afternoon.csv",
            ],
        })
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            metadata = prepare_dataset(
                frame,
                output,
                split_strategy="by-file",
                test_file_prefix="Friday",
            )
            train = pd.read_csv(output / "train.csv")
            test = pd.read_csv(output / "test.csv")

            self.assertEqual(metadata["split_strategy"], "by-file")
            self.assertNotIn("source_file", metadata["raw_feature_columns"])
            self.assertFalse(any(
                column.startswith("source_file")
                for column in metadata["transformed_feature_columns"]
            ))
            self.assertFalse(train["source_file"].str.startswith("Friday").any())
            self.assertTrue(test["source_file"].str.startswith("Friday").all())

    def test_prepare_dataset_splits_each_label_by_its_own_timeline(self):
        frame = pd.DataFrame({
            "feature": range(11),
            "Label": ["BENIGN"] * 5 + ["DoS Hulk"] * 5 + ["Heartbleed"],
            "Timestamp": [
                "3/7/2017 8:00", "3/7/2017 8:01", "3/7/2017 8:02",
                "3/7/2017 8:03", "3/7/2017 8:04",
                "5/7/2017 9:00", "5/7/2017 9:01", "5/7/2017 9:02",
                "5/7/2017 9:03", "5/7/2017 9:04",
                "5/7/2017 3:12",
            ],
        })
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            metadata = prepare_dataset(
                frame, output, split_strategy="temporal-per-class", test_size=0.2,
            )
            train = pd.read_csv(output / "train.csv")
            test = pd.read_csv(output / "test.csv")

            self.assertEqual(metadata["split_strategy"], "temporal-per-class")
            self.assertNotIn("timestamp", metadata["raw_feature_columns"])

            # a single-row label can't be held out; it must stay in train only
            self.assertIn("Heartbleed", train["label"].tolist())
            self.assertNotIn("Heartbleed", test["label"].tolist())

            # labels with enough rows appear on both sides
            for label in ("BENIGN", "DoS Hulk"):
                self.assertIn(label, train["label"].tolist())
                self.assertIn(label, test["label"].tolist())

            self.assertEqual(metadata["train_rows"], 9)
            self.assertEqual(metadata["test_rows"], 2)

    def test_temporal_split_requires_timestamp_column(self):
        frame = pd.DataFrame({"feature": [1, 2], "Label": ["BENIGN", "DoS"]})
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "timestamp"):
                prepare_dataset(
                    frame, Path(directory), split_strategy="temporal-per-class"
                )


if __name__ == "__main__":
    unittest.main()
