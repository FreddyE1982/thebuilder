import os
import sys
import unittest
from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from rest_api import GymAPI


class AsyncSetEndpointsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = "test_async_sets.db"
        self.yaml_path = "test_async_sets.yaml"
        for p in [self.db_path, self.yaml_path]:
            if os.path.exists(p):
                os.remove(p)
        self.api = GymAPI(db_path=self.db_path, yaml_path=self.yaml_path)
        self.client = TestClient(self.api.app)

    def tearDown(self) -> None:
        for p in [self.db_path, self.yaml_path]:
            if os.path.exists(p):
                os.remove(p)

    def test_add_update_list_set(self) -> None:
        wid = self.client.post("/workouts").json()["id"]
        eid = self.client.post(
            f"/workouts/{wid}/exercises",
            params={"name": "Bench", "equipment": "Bar"},
        ).json()["id"]
        sid = self.client.post(
            f"/exercises/{eid}/sets",
            params={"reps": 5, "weight": 80.0, "rpe": 7},
        ).json()["id"]
        detail = self.client.get(f"/sets/{sid}").json()
        self.assertEqual(detail["reps"], 5)
        self.client.put(
            f"/sets/{sid}",
            params={"reps": 6, "weight": 85.0, "rpe": 8},
        )
        data = self.client.get(f"/exercises/{eid}/sets").json()
        self.assertEqual(data[0]["weight"], 85.0)


if __name__ == "__main__":
    unittest.main()
