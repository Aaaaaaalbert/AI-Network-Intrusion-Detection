import unittest

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from src.leave_one_attack_out import (
    binary_metrics,
    evaluate_seen_control,
    fit_seen_control,
    multiclass_metrics,
    run_one_attack,
    split_benign_pool,
    training_frame_for_attack,
    wilson_interval,
)


class LeaveOneAttackOutTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(42)
        rows = []
        priority = 0.0
        for label, is_attack, centre in (
            ("BENIGN", 0, 0.0),
            ("Attack A", 1, 3.0),
            ("Attack B", 1, 6.0),
        ):
            for _ in range(30):
                rows.append({
                    "feature_1": rng.normal(centre, 0.3),
                    "feature_2": rng.normal(centre, 0.3),
                    "label": label,
                    "is_attack": is_attack,
                    "source_file": f"{label}.csv",
                    "__priority": priority,
                })
                priority += 0.001
        self.data = pd.DataFrame(rows)

    def test_wilson_interval_contains_observed_rate(self):
        low, high = wilson_interval(80, 100)
        self.assertLess(low, 0.8)
        self.assertGreater(high, 0.8)

    def test_training_frame_fully_excludes_held_out_attack(self):
        benign_train, _ = split_benign_pool(self.data, 10, 20)
        training = training_frame_for_attack(
            self.data, benign_train, "Attack A", max_train_per_class=20
        )
        self.assertNotIn("Attack A", training["label"].unique())
        self.assertIn("Attack B", training["label"].unique())
        self.assertEqual(int((training["is_attack"] == 0).sum()), 20)

    def test_metric_helpers_report_high_confidence_misses(self):
        binary = binary_metrics(
            np.array([1, 0, 0]),
            np.array([0.9, 0.95, 0.6]),
            np.array([0.9, 0.05, 0.4]),
            np.array([0, 1]),
            confidence_threshold=0.8,
        )
        self.assertAlmostEqual(binary["unseen_attack_recall"], 1 / 3)
        self.assertAlmostEqual(binary["high_confidence_false_negative_rate"], 1 / 3)
        self.assertAlmostEqual(binary["benign_false_positive_rate"], 0.5)

        multiclass = multiclass_metrics(
            np.array(["BENIGN", "Known", "BENIGN"]),
            np.array([0.9, 0.7, 0.6]),
            normal_label="BENIGN",
            confidence_threshold=0.8,
        )
        self.assertAlmostEqual(multiclass["predicted_as_benign_rate"], 2 / 3)
        self.assertAlmostEqual(multiclass["high_confidence_benign_rate"], 1 / 3)

    def test_end_to_end_run_never_trains_on_held_out_label(self):
        benign_train, benign_test = split_benign_pool(self.data, 10, 20)

        def factory():
            return RandomForestClassifier(n_estimators=5, random_state=42)

        result, predictions = run_one_attack(
            self.data,
            self.data,
            benign_train,
            benign_test,
            held_out_attack="Attack A",
            max_train_per_class=20,
            max_holdout_per_attack=10,
            confidence_threshold=0.8,
            model_factory=factory,
        )
        self.assertNotIn("Attack A", result["training_labels"])
        self.assertEqual(result["holdout_test_rows"], 10)
        self.assertEqual(len(predictions), 10)
        self.assertTrue((predictions["held_out_attack"] == "Attack A").all())

    def test_matched_control_has_seen_the_attack_on_same_evaluation_rows(self):
        benign_train, benign_test = split_benign_pool(self.data, 10, 20)

        def factory():
            return RandomForestClassifier(n_estimators=5, random_state=42)

        scaler, binary, multiclass, features = fit_seen_control(
            self.data, benign_train, max_train_per_class=20, model_factory=factory
        )
        control = evaluate_seen_control(
            scaler,
            binary,
            multiclass,
            features,
            self.data,
            benign_test,
            held_out_attack="Attack A",
            max_holdout_per_attack=10,
            confidence_threshold=0.8,
        )
        self.assertGreaterEqual(control["binary"]["unseen_attack_recall"], 0.9)
        self.assertGreaterEqual(control["multiclass_correct_recall"], 0.9)


if __name__ == "__main__":
    unittest.main()
