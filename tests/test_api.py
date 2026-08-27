import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = PROJECT_ROOT / "models" / "multiclass_random" / "random_forest.joblib"
PREPROCESSOR_PATH = PROJECT_ROOT / "dataset" / "processed" / "preprocessor.joblib"

ARTIFACTS_MISSING = not (MODEL_PATH.exists() and PREPROCESSOR_PATH.exists())
SKIP_REASON = (
    "trained model/preprocessor are not committed to git (derived from the real "
    "CIC-IDS2017 dataset); run src.prepare_data and src.train_baseline first"
)


@unittest.skipIf(ARTIFACTS_MISSING, SKIP_REASON)
class PredictionApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from api.main import app, feature_names, samples_df

        cls.client = TestClient(app)
        cls.feature_names = feature_names
        cls.samples_df = samples_df

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_predict_on_a_real_flow_returns_label_and_confidence(self):
        row = self.samples_df.iloc[0]
        features = row[self.feature_names].to_dict()

        response = self.client.post("/predict", json=features)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("is_attack", body)
        self.assertIn("attack_type", body)
        self.assertGreaterEqual(body["confidence"], 0.0)
        self.assertLessEqual(body["confidence"], 1.0)

    def test_predict_rejects_missing_or_unknown_features(self):
        response = self.client.post("/predict", json={"not_a_feature": 1})
        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertIn("not_a_feature", detail["unknown_features"])
        self.assertTrue(detail["missing_features"])


if __name__ == "__main__":
    unittest.main()
