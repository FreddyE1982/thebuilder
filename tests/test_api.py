import os
import datetime
import unittest
from fastapi.testclient import TestClient
from rest_api import GymAPI


class APITestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = "test_workout.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.api = GymAPI(db_path=self.db_path)
        self.client = TestClient(self.api.app)

    def tearDown(self) -> None:
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_full_workflow(self) -> None:
        today = datetime.date.today().isoformat()

        response = self.client.post("/workouts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": 1})

        response = self.client.get("/workouts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{"id": 1, "date": today}])

        response = self.client.post(
            "/workouts/1/exercises", params={"name": "Bench Press"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": 1})

        response = self.client.get("/workouts/1/exercises")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{"id": 1, "name": "Bench Press"}])

        response = self.client.post(
            "/exercises/1/sets", params={"reps": 10, "weight": 100.0}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": 1})

        response = self.client.get("/exercises/1/sets")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), [{"id": 1, "reps": 10, "weight": 100.0}]
        )

        response = self.client.put(
            "/sets/1", params={"reps": 12, "weight": 105.0}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "updated"})

        response = self.client.get("/exercises/1/sets")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), [{"id": 1, "reps": 12, "weight": 105.0}]
        )

        response = self.client.delete("/sets/1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "deleted"})

        response = self.client.get("/exercises/1/sets")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

        response = self.client.delete("/exercises/1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "deleted"})

        response = self.client.get("/workouts/1/exercises")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])
