import os
import unittest
from fastapi.testclient import TestClient
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from rest_api import GymAPI

class BulkCompleteTest(unittest.TestCase):
    def setUp(self):
        self.db = "test_complete.db"
        self.yaml = "test_complete.yaml"
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

    def test_bulk_complete(self):
        wid = self.client.post("/workouts").json()["id"]
        eid = self.client.post(
            f"/workouts/{wid}/exercises",
            params={"name": "Bench", "equipment": "Bar"},
        ).json()["id"]
        ids = []
        for _ in range(2):
            r = self.client.post(f"/exercises/{eid}/sets", params={"reps": 5, "weight": 50.0, "rpe": 8})
            ids.append(r.json()["id"])
        self.client.post("/sets/bulk_complete", params={"set_ids": ",".join(str(i) for i in ids)})
        data = self.client.get(f"/exercises/{eid}/sets").json()
        for entry in data:
            self.assertIn("end_time", entry)

if __name__ == "__main__":
    unittest.main()
