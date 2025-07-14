import os
import sys
import datetime
import unittest
import sqlite3
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
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": 1})

        response = self.client.get("/workouts/1/exercises")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), [{"id": 1, "name": "Bench Press", "equipment": "Olympic Barbell"}]
        )

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

    def test_general_settings(self) -> None:
        resp = self.client.get("/settings/general")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json(), {"body_weight": 80.0, "months_active": 1.0}
        )

        resp = self.client.post(
            "/settings/general",
            params={"body_weight": 85.5, "months_active": 6.0},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "updated"})

        resp = self.client.get("/settings/general")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json(), {"body_weight": 85.5, "months_active": 6.0}
        )

    def test_plan_workflow(self) -> None:
        plan_date = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

        response = self.client.post("/planned_workouts", params={"date": plan_date})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": 1})

        response = self.client.get("/planned_workouts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{"id": 1, "date": plan_date}])

        response = self.client.post(
            "/planned_workouts/1/exercises",
            params={"name": "Squat", "equipment": "Olympic Barbell"},
        )
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
        self.assertEqual(
            response.json(),
            [{"id": 1, "name": "Squat", "equipment": "Olympic Barbell"}],
        )

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

    def test_equipment_endpoints(self) -> None:
        response = self.client.get("/equipment/types")
        self.assertEqual(response.status_code, 200)
        types = response.json()
        self.assertIn("Free Weights", types)

        response = self.client.get(
            "/equipment", params={"equipment_type": "Free Weights", "prefix": "Olympic"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Olympic Barbell", response.json())

        response = self.client.get("/equipment/Olympic Barbell")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "Olympic Barbell")
        self.assertIn("Pectoralis Major", data["muscles"])

        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises", params={"name": "Clean", "equipment": "Olympic Barbell"}
        )
        resp = self.client.get("/workouts/1/exercises")
        self.assertEqual(
            resp.json(),
            [{"id": 1, "name": "Clean", "equipment": "Olympic Barbell"}],
        )

        # custom equipment lifecycle
        resp = self.client.post(
            "/equipment",
            params={
                "equipment_type": "Custom",
                "name": "My Eq",
                "muscles": "Foo|Bar",
            },
        )
        self.assertEqual(resp.status_code, 200)
        eq_id = resp.json()["id"]
        self.assertIsInstance(eq_id, int)

        resp = self.client.put(
            "/equipment/My Eq",
            params={
                "equipment_type": "Custom",
                "muscles": "Foo|Baz",
                "new_name": "My Eq2",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "updated"})

        resp = self.client.delete("/equipment/My Eq2")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "deleted"})

        # ensure imported equipment cannot be removed
        resp = self.client.delete("/equipment/Olympic Barbell")
        self.assertEqual(resp.status_code, 400)

    def test_schema_migration(self) -> None:
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """CREATE TABLE workouts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL
                );"""
        )
        cur.execute(
            """CREATE TABLE exercises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workout_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    FOREIGN KEY(workout_id) REFERENCES workouts(id) ON DELETE CASCADE
                );"""
        )
        cur.execute(
            """CREATE TABLE sets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exercise_id INTEGER NOT NULL,
                    reps INTEGER NOT NULL,
                    weight REAL NOT NULL,
                    rpe INTEGER NOT NULL,
                    FOREIGN KEY(exercise_id) REFERENCES exercises(id) ON DELETE CASCADE
                );"""
        )
        today = datetime.date.today().isoformat()
        cur.execute("INSERT INTO workouts (date) VALUES (?);", (today,))
        cur.execute("INSERT INTO exercises (workout_id, name) VALUES (1, 'Legacy Ex');")
        cur.execute(
            "INSERT INTO sets (exercise_id, reps, weight, rpe) VALUES (1, 8, 80.0, 7);"
        )
        conn.commit()
        conn.close()

        api = GymAPI(db_path=self.db_path)
        client = TestClient(api.app)

        resp = client.get("/exercises/1/sets")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [{"id": 1, "reps": 8, "weight": 80.0, "rpe": 7}])

        resp = client.get("/sets/1")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("planned_set_id", data)
        self.assertIn("diff_reps", data)

    def test_exercise_catalog_endpoints(self) -> None:
        resp = self.client.get("/exercise_catalog/muscle_groups")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Chest", resp.json())

        resp = self.client.get("/exercise_catalog", params={"muscle_groups": "Chest"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Barbell Bench Press", resp.json())

        resp = self.client.get("/exercise_catalog/Barbell Bench Press")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("Pectoralis Major", data["primary_muscle"])

        resp = self.client.post(
            "/exercise_catalog",
            params={
                "muscle_group": "Test",
                "name": "My Ex",
                "variants": "Var1|Var2",
                "equipment_names": "Olympic Barbell",
                "primary_muscle": "Foo",
            },
        )
        self.assertEqual(resp.status_code, 200)
        ex_id = resp.json()["id"]
        self.assertIsInstance(ex_id, int)

        resp = self.client.put(
            "/exercise_catalog/My Ex",
            params={
                "muscle_group": "Test",
                "variants": "Var1",
                "equipment_names": "Olympic Barbell",
                "primary_muscle": "Foo",
                "secondary_muscle": "",
                "tertiary_muscle": "",
                "other_muscles": "",
                "new_name": "My Ex2",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "updated"})

        resp = self.client.delete("/exercise_catalog/My Ex2")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "deleted"})

        resp = self.client.delete("/exercise_catalog/Barbell Bench Press")
        self.assertEqual(resp.status_code, 400)

    def test_muscle_alias(self) -> None:
        resp = self.client.get("/muscles")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Biceps Brachii", resp.json())

        resp = self.client.post(
            "/muscles/alias", params={"new_name": "My Biceps", "existing": "Biceps Brachii"}
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.client.post(
            "/muscles/link", params={"name1": "My Biceps", "name2": "Brachialis"}
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get("/equipment", params={"muscles": "My Biceps"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("EZ Curl Bar", resp.json())

        resp = self.client.get(
            "/exercise_catalog", params={"muscles": "My Biceps"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Pull-up", resp.json())

    def test_exercise_alias(self) -> None:
        resp = self.client.post(
            "/exercise_names/alias",
            params={"new_name": "My Pulls", "existing": "Pull-up"},
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.client.post(
            "/exercise_names/link",
            params={"name1": "My Pulls", "name2": "Chin-up"},
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get("/exercise_catalog/My Pulls")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("Latissimus Dorsi", data["primary_muscle"])

        resp = self.client.get(
            "/exercise_catalog",
            params={"muscle_groups": "Back"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("My Pulls", resp.json())

    def test_statistics_endpoints(self) -> None:
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 10, "weight": 100.0, "rpe": 8},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 8, "weight": 110.0, "rpe": 9},
        )

        resp = self.client.get(
            "/stats/exercise_summary",
            params={"exercise": "Bench Press"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        summary = data[0]
        self.assertEqual(summary["exercise"], "Bench Press")
        self.assertEqual(summary["sets"], 2)
        self.assertAlmostEqual(summary["volume"], 1880.0)
        self.assertAlmostEqual(summary["avg_rpe"], 8.5)
        self.assertAlmostEqual(summary["max_1rm"], 139.3, places=1)

        resp = self.client.get(
            "/stats/progression",
            params={"exercise": "Bench Press"},
        )
        self.assertEqual(resp.status_code, 200)
        prog = resp.json()
        self.assertEqual(len(prog), 1)
        self.assertAlmostEqual(prog[0]["est_1rm"], 139.3, places=1)

