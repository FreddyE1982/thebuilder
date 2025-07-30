import os
import unittest
from fastapi.testclient import TestClient
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from rest_api import GymAPI

class WorkoutRenameTest(unittest.TestCase):
    def setUp(self):
        self.db = "test_rename.db"
        self.yaml = "test_rename.yaml"
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

    def test_rename_workout(self):
        wid = self.client.post("/workouts").json()["id"]
        resp = self.client.put(f"/workouts/{wid}/name", params={"name": "Test"})
        self.assertEqual(resp.status_code, 200)
        data = self.client.get(f"/workouts/{wid}").json()
        self.assertEqual(data["name"], "Test")

if __name__ == "__main__":
    unittest.main()
