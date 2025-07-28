import os
import sqlite3
import unittest
from fastapi.testclient import TestClient
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from rest_api import GymAPI


class APIIntegrationDBTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = "test_integration.db"
        self.yaml_path = "test_integration.yaml"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        if os.path.exists(self.yaml_path):
            os.remove(self.yaml_path)
        self.api = GymAPI(db_path=self.db_path, yaml_path=self.yaml_path)
        self.client = TestClient(self.api.app)
        reg = self.client.post(
            "/users/register",
            json={"username": "test", "password": "test"},
        )
        assert reg.status_code == 200
        login = self.client.post(
            "/token",
            json={"username": "test", "password": "test"},
        )
        assert login.status_code == 200
        token = login.json()["token"]
        self.client.headers.update({"Authorization": token})

    def tearDown(self) -> None:
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        if os.path.exists(self.yaml_path):
            os.remove(self.yaml_path)

    def _count_rows(self, table: str) -> int:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {table};")
        count = cur.fetchone()[0]
        conn.close()
        return count

    def test_workout_creation_persists(self) -> None:
        resp = self.client.post("/workouts")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"id": 1})
        self.assertEqual(self._count_rows("workouts"), 1)

    def test_add_exercise_and_set(self) -> None:
        self.client.post("/workouts")
        resp = self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench", "equipment": "Olympic Barbell"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"id": 1})
        self.assertEqual(self._count_rows("exercises"), 1)
        resp = self.client.post(
            "/exercises/1/sets", params={"reps": 5, "weight": 100.0, "rpe": 8}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"id": 1})
        self.assertEqual(self._count_rows("sets"), 1)


if __name__ == "__main__":
    unittest.main()
