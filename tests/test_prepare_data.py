import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.prepare_data import clean_data, demo_data, prepare_dataset


class PrepareDataTests(unittest.TestCase):
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
