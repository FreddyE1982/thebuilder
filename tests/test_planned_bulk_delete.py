import os
import unittest
from fastapi.testclient import TestClient
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from rest_api import GymAPI

class PlannedBulkDeleteTest(unittest.TestCase):
    def setUp(self):
        self.db = "test_bulk.db"
        self.yaml = "test_bulk.yaml"
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

    def test_delete_bulk(self):
        ids = []
        for _ in range(3):
            resp = self.client.post("/planned_workouts", params={"date": "2024-01-01"})
            ids.append(resp.json()["id"])
        self.client.post("/planned_workouts/delete_bulk", json=",".join(str(i) for i in ids))
        self.assertEqual(self.client.get("/planned_workouts").json(), [])

if __name__ == "__main__":
    unittest.main()
