import os
import sys
import datetime
import unittest
from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
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
            "/exercises/1/sets",
            params={"reps": 10, "weight": 100.0, "rpe": 8},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": 1})

        response = self.client.get("/exercises/1/sets")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), [{"id": 1, "reps": 10, "weight": 100.0, "rpe": 8}]
        )

        response = self.client.put(
            "/sets/1", params={"reps": 12, "weight": 105.0, "rpe": 9}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "updated"})

        response = self.client.get("/exercises/1/sets")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), [{"id": 1, "reps": 12, "weight": 105.0, "rpe": 9}]
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

    def test_delete_endpoints(self) -> None:
        plan_date = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

        self.client.post("/workouts")
        self.client.post("/planned_workouts", params={"date": plan_date})

        response = self.client.post("/settings/delete_all", params={"confirmation": "Yes, I confirm"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "deleted"})

        response = self.client.get("/workouts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

        response = self.client.get("/planned_workouts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

        self.client.post("/workouts")
        self.client.post("/planned_workouts", params={"date": plan_date})

        response = self.client.post("/settings/delete_logged", params={"confirmation": "Yes, I confirm"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "deleted"})

        response = self.client.get("/workouts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

        response = self.client.get("/planned_workouts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

        response = self.client.post("/settings/delete_planned", params={"confirmation": "Yes, I confirm"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "deleted"})

        response = self.client.get("/planned_workouts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_plan_workflow(self) -> None:
        plan_date = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

        response = self.client.post("/planned_workouts", params={"date": plan_date})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": 1})

        response = self.client.get("/planned_workouts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{"id": 1, "date": plan_date}])

        response = self.client.post("/planned_workouts/1/exercises", params={"name": "Squat"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": 1})

        response = self.client.post("/planned_exercises/1/sets", params={"reps": 5, "weight": 150.0, "rpe": 8})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": 1})

        response = self.client.post("/planned_workouts/1/use")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": 1})

        response = self.client.get("/workouts/1/exercises")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{"id": 1, "name": "Squat"}])

        response = self.client.get("/exercises/1/sets")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{"id": 1, "reps": 5, "weight": 150.0, "rpe": 8}])

        response = self.client.put("/sets/1", params={"reps": 6, "weight": 160.0, "rpe": 9})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "updated"})

        response = self.client.get("/sets/1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "id": 1,
                "reps": 6,
                "weight": 160.0,
                "rpe": 9,
                "planned_set_id": 1,
                "diff_reps": 1,
                "diff_weight": 10.0,
                "diff_rpe": 1,
            },
        )
