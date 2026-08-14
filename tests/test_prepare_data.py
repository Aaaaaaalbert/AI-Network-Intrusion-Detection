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


if __name__ == "__main__":
    unittest.main()
