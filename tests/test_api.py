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

        response = self.client.get("/workouts/1/export_csv")
        self.assertEqual(response.status_code, 200)
        csv_text = response.text.strip().splitlines()
        self.assertEqual(csv_text[0], "Exercise,Equipment,Reps,Weight,RPE,Start,End")
        self.assertIn("Bench Press", csv_text[1])

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
        self.client.post(
            "/planned_workouts",
            params={"date": plan_date, "training_type": "strength"},
        )

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
        self.client.post(
            "/planned_workouts",
            params={"date": plan_date, "training_type": "strength"},
        )

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
            resp.json(),
            {
                "body_weight": 80.0,
                "months_active": 1.0,
                "theme": "light",
                "game_enabled": 0.0,
            },
        )

        resp = self.client.post(
            "/settings/general",
            params={"body_weight": 85.5, "months_active": 6.0, "theme": "dark"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "updated"})

        resp = self.client.get("/settings/general")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json(),
            {
                "body_weight": 85.5,
                "months_active": 6.0,
                "theme": "dark",
                "game_enabled": 0.0,
            },
        )

    def test_plan_workflow(self) -> None:
        plan_date = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

        response = self.client.post(
            "/planned_workouts",
            params={"date": plan_date, "training_type": "hypertrophy"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": 1})

        response = self.client.get("/planned_workouts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [{"id": 1, "date": plan_date, "training_type": "hypertrophy"}],
        )

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

        response = self.client.get("/workouts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [{"id": 1, "date": plan_date}],
        )
        resp_detail = self.client.get("/workouts/1")
        self.assertEqual(resp_detail.status_code, 200)
        self.assertEqual(resp_detail.json()["training_type"], "hypertrophy")

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
                "start_time": None,
                "end_time": None,
            },
        )

        new_date = (datetime.date.today() + datetime.timedelta(days=2)).isoformat()
        resp = self.client.put(
            "/planned_workouts/1",
            params={"date": new_date, "training_type": "strength"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "updated"})

        dup_date = (datetime.date.today() + datetime.timedelta(days=3)).isoformat()
        resp = self.client.post(
            "/planned_workouts/1/duplicate",
            params={"date": dup_date},
        )
        self.assertEqual(resp.status_code, 200)
        dup_id = resp.json()["id"]
        self.assertEqual(dup_id, 2)

        resp = self.client.delete("/planned_workouts/1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "deleted"})

        resp = self.client.get("/planned_workouts")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json(),
            [{"id": dup_id, "date": dup_date, "training_type": "strength"}],
        )

    def test_planned_set_update_and_get(self) -> None:
        plan_date = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        resp = self.client.post(
            "/planned_workouts",
            params={"date": plan_date, "training_type": "strength"},
        )
        self.assertEqual(resp.status_code, 200)
        plan_id = resp.json()["id"]

        resp = self.client.post(
            f"/planned_workouts/{plan_id}/exercises",
            params={"name": "Bench", "equipment": "Olympic Barbell"},
        )
        self.assertEqual(resp.status_code, 200)
        ex_id = resp.json()["id"]

        resp = self.client.post(
            f"/planned_exercises/{ex_id}/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        self.assertEqual(resp.status_code, 200)
        set_id = resp.json()["id"]

        resp = self.client.put(
            f"/planned_sets/{set_id}",
            params={"reps": 6, "weight": 105.0, "rpe": 9},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "updated"})

        resp = self.client.get(f"/planned_sets/{set_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json(),
            {
                "id": set_id,
                "planned_exercise_id": ex_id,
                "reps": 6,
                "weight": 105.0,
                "rpe": 9,
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

    def test_gamification(self) -> None:
        resp = self.client.get("/gamification")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["enabled"])

        self.client.post("/gamification/enable", params={"enabled": True})
        resp = self.client.get("/gamification")
        self.assertTrue(resp.json()["enabled"])

        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 10, "weight": 100.0, "rpe": 8},
        )

        resp = self.client.get("/gamification")
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(resp.json()["points"], 101.31, places=2)

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

        resp = self.client.get("/stats/daily_volume")
        self.assertEqual(resp.status_code, 200)
        daily = resp.json()
        self.assertEqual(len(daily), 1)
        self.assertAlmostEqual(daily[0]["volume"], 1880.0)

        resp = self.client.get("/stats/equipment_usage")
        self.assertEqual(resp.status_code, 200)
        eq_stats = resp.json()
        self.assertEqual(len(eq_stats), 1)
        self.assertEqual(eq_stats[0]["equipment"], "Olympic Barbell")
        self.assertEqual(eq_stats[0]["sets"], 2)

        resp = self.client.get(
            "/stats/rpe_distribution",
            params={"exercise": "Bench Press"},
        )
        self.assertEqual(resp.status_code, 200)
        rpe = resp.json()
        self.assertEqual(len(rpe), 2)
        self.assertEqual(rpe[0]["rpe"], 8)
        self.assertEqual(rpe[0]["count"], 1)
        self.assertEqual(rpe[1]["rpe"], 9)
        self.assertEqual(rpe[1]["count"], 1)

        resp = self.client.get(
            "/stats/exercise_history",
            params={"exercise": "Bench Press"},
        )
        self.assertEqual(resp.status_code, 200)
        history = resp.json()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["reps"], 10)
        self.assertEqual(history[1]["weight"], 110.0)

        resp = self.client.get(
            "/stats/reps_distribution",
            params={"exercise": "Bench Press"},
        )
        self.assertEqual(resp.status_code, 200)
        rep_dist = resp.json()
        self.assertEqual(len(rep_dist), 2)
        self.assertEqual(rep_dist[0]["reps"], 8)
        self.assertEqual(rep_dist[0]["count"], 1)
        self.assertEqual(rep_dist[1]["reps"], 10)
        self.assertEqual(rep_dist[1]["count"], 1)

        resp = self.client.get(
            "/prediction/progress",
            params={"exercise": "Bench Press", "weeks": 2, "workouts": 1},
        )
        self.assertEqual(resp.status_code, 200)
        forecast = resp.json()
        self.assertEqual(len(forecast), 2)
        self.assertAlmostEqual(forecast[0]["est_1rm"], 139.3, places=1)
        self.assertAlmostEqual(forecast[1]["est_1rm"], 139.3, places=1)

        resp = self.client.get("/stats/overview")
        self.assertEqual(resp.status_code, 200)
        overview = resp.json()
        self.assertEqual(overview["workouts"], 1)
        self.assertAlmostEqual(overview["volume"], 1880.0)
        self.assertAlmostEqual(overview["avg_rpe"], 8.5)
        self.assertEqual(overview["exercises"], 1)

        resp = self.client.get(
            "/stats/personal_records",
            params={"exercise": "Bench Press"},
        )
        self.assertEqual(resp.status_code, 200)
        records = resp.json()
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertEqual(rec["exercise"], "Bench Press")
        self.assertEqual(rec["reps"], 8)
        self.assertAlmostEqual(rec["weight"], 110.0)
        self.assertAlmostEqual(rec["est_1rm"], 139.3, places=1)

    def test_progress_insights(self) -> None:
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
            "/stats/progress_insights",
            params={"exercise": "Bench Press"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["trend"], "insufficient_data")
        self.assertIn("plateau_score", data)

    def test_timestamps(self) -> None:
        resp = self.client.post("/workouts", params={"training_type": "strength"})
        self.assertEqual(resp.status_code, 200)
        wid = resp.json()["id"]

        resp = self.client.post(f"/workouts/{wid}/start")
        self.assertEqual(resp.status_code, 200)
        start_ts = resp.json()["timestamp"]

        resp = self.client.get(f"/workouts/{wid}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["start_time"], start_ts)
        self.assertEqual(resp.json()["training_type"], "strength")

        resp = self.client.post(f"/workouts/{wid}/finish")
        self.assertEqual(resp.status_code, 200)
        end_ts = resp.json()["timestamp"]

        resp = self.client.get(f"/workouts/{wid}")
        self.assertEqual(resp.json()["end_time"], end_ts)

        self.client.post(
            f"/workouts/{wid}/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        resp = self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        sid = resp.json()["id"]

        resp = self.client.post(f"/sets/{sid}/start")
        self.assertEqual(resp.status_code, 200)
        set_start = resp.json()["timestamp"]

        resp = self.client.get(f"/sets/{sid}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["start_time"], set_start)

        resp = self.client.post(f"/sets/{sid}/finish")
        self.assertEqual(resp.status_code, 200)
        set_end = resp.json()["timestamp"]

        resp = self.client.get(f"/sets/{sid}")
        self.assertEqual(resp.json()["end_time"], set_end)

    def test_training_type(self) -> None:
        resp = self.client.post("/workouts", params={"training_type": "hypertrophy"})
        self.assertEqual(resp.status_code, 200)
        wid = resp.json()["id"]

        resp = self.client.get(f"/workouts/{wid}")
        self.assertEqual(resp.json()["training_type"], "hypertrophy")

        resp = self.client.put(
            f"/workouts/{wid}/type", params={"training_type": "strength"}
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get(f"/workouts/{wid}")
        self.assertEqual(resp.json()["training_type"], "strength")

    def test_backdated_workout(self) -> None:
        past_date = (datetime.date.today() - datetime.timedelta(days=3)).isoformat()
        resp = self.client.post(
            "/workouts",
            params={"date": past_date, "training_type": "strength"},
        )
        self.assertEqual(resp.status_code, 200)
        wid = resp.json()["id"]

        self.client.post(
            f"/workouts/{wid}/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/1/sets", params={"reps": 5, "weight": 100.0, "rpe": 8}
        )

        resp = self.client.get("/workouts")
        self.assertEqual(resp.json(), [{"id": wid, "date": past_date}])

        resp = self.client.get("/stats/daily_volume")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()[0]["date"], past_date)

    def test_workout_history_endpoint(self) -> None:
        d1 = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        d2 = datetime.date.today().isoformat()

        self.client.post("/workouts", params={"date": d1, "training_type": "strength"})
        self.client.post("/workouts", params={"date": d2, "training_type": "hypertrophy"})
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )

        resp = self.client.get(
            "/workouts/history",
            params={"start_date": d1, "end_date": d2},
        )
        self.assertEqual(resp.status_code, 200)
        history = sorted(resp.json(), key=lambda x: x["id"])
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["training_type"], "strength")
        self.assertEqual(history[0]["volume"], 500.0)
        self.assertEqual(history[0]["sets"], 1)
        self.assertEqual(history[0]["avg_rpe"], 8.0)

    def test_pyramid_tests(self) -> None:
        today = datetime.date.today().isoformat()
        resp = self.client.post(
            "/pyramid_tests",
            params={
                "weights": "100|110",
                "exercise_name": "Bench Press",
                "equipment_name": "Olympic Barbell",
                "starting_weight": 100.0,
                "failed_weight": 115.0,
            },
        )
        self.assertEqual(resp.status_code, 200)
        tid1 = resp.json()["id"]

        resp = self.client.get("/pyramid_tests")
        self.assertEqual(resp.status_code, 200)
        history = resp.json()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["id"], tid1)
        self.assertEqual(history[0]["date"], today)
        self.assertEqual(history[0]["weights"], [100.0, 110.0])

        resp = self.client.post("/pyramid_tests", params={"weights": "120"})
        self.assertEqual(resp.status_code, 200)
        tid2 = resp.json()["id"]
        self.assertEqual(tid2, tid1 + 1)

        resp_invalid = self.client.post(
            "/pyramid_tests",
            params={"weights": "130|120", "starting_weight": 100.0, "max_achieved": 90.0},
        )
        self.assertEqual(resp_invalid.status_code, 400)

        resp = self.client.get("/pyramid_tests")
        self.assertEqual(resp.status_code, 200)
        history = resp.json()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["weights"], [120.0])
        self.assertEqual(history[1]["weights"], [100.0, 110.0])

    def test_pyramid_tests_full(self) -> None:
        resp = self.client.post(
            "/pyramid_tests",
            params={
                "weights": "100|110",
                "exercise_name": "Bench",
                "equipment_name": "Olympic Barbell",
                "starting_weight": 100.0,
                "failed_weight": 115.0,
                "max_achieved": 110.0,
                "test_duration_minutes": 10,
                "rest_between_attempts": "120s",
                "rpe_per_attempt": "8|9",
                "time_of_day": "morning",
                "sleep_hours": 7.5,
                "stress_level": 2,
                "nutrition_quality": 4,
            },
        )
        self.assertEqual(resp.status_code, 200)
        tid = resp.json()["id"]

        resp = self.client.get("/pyramid_tests/full")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()[0]
        self.assertEqual(data["id"], tid)
        self.assertEqual(data["exercise_name"], "Bench")
        self.assertEqual(data["equipment_name"], "Olympic Barbell")
        self.assertEqual(data["weights"], [100.0, 110.0])
        self.assertEqual(data["starting_weight"], 100.0)
        self.assertEqual(data["failed_weight"], 115.0)
        self.assertEqual(data["max_achieved"], 110.0)
        self.assertEqual(data["test_duration_minutes"], 10)
        self.assertEqual(data["rest_between_attempts"], "120s")
        self.assertEqual(data["rpe_per_attempt"], "8|9")
        self.assertEqual(data["time_of_day"], "morning")
        self.assertAlmostEqual(data["sleep_hours"], 7.5)
        self.assertEqual(data["stress_level"], 2)
        self.assertEqual(data["nutrition_quality"], 4)

    def test_exercise_catalog_prefix_filter(self) -> None:
        resp = self.client.get(
            "/exercise_catalog",
            params={"prefix": "Barbell"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Barbell Bench Press", resp.json())

