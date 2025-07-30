import os
import unittest
from fastapi.testclient import TestClient
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from rest_api import GymAPI

class ExerciseFilterNoEquipmentTest(unittest.TestCase):
    def setUp(self):
        self.db = "test_filter.db"
        self.yaml = "test_filter.yaml"
        if os.path.exists(self.db):
            os.remove(self.db)
        if os.path.exists(self.yaml):
            os.remove(self.yaml)
        self.api = GymAPI(db_path=self.db, yaml_path=self.yaml)
        self.client = TestClient(self.api.app)

    def tearDown(self):
        if os.path.exists(self.db):
            os.remove(self.db)
        if os.path.exists(self.yaml):
            os.remove(self.yaml)

    def test_filter_no_equipment(self):
        self.client.post(
            "/exercise_catalog",
            params={
                "muscle_group": "Arms",
                "name": "Bodyweight Curl",
                "variants": "",
                "equipment_names": "",
                "primary_muscle": "Biceps Brachii",
            },
        )
        resp = self.client.get("/exercise_catalog", params={"no_equipment": True})
        self.assertIn("Bodyweight Curl", resp.json())

if __name__ == "__main__":
    unittest.main()
