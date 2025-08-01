import os
import sys
import datetime
import unittest
import sqlite3
import shutil
import subprocess
import io
from fastapi.testclient import TestClient
import yaml
import json

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from rest_api import GymAPI
from tools import MathTools, ExercisePrescription


class APITestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = "test_workout.db"
        self.yaml_path = "test_settings.yaml"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        if os.path.exists(self.yaml_path):
            os.remove(self.yaml_path)
        self.api = GymAPI(
            db_path=self.db_path,
            yaml_path=self.yaml_path,
            start_scheduler=False,
            rate_limit=None,
        )
        self.client = TestClient(self.api.app)

    def tearDown(self) -> None:
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        if os.path.exists(self.yaml_path):
            os.remove(self.yaml_path)

    def test_full_workflow(self) -> None:
        today = datetime.date.today().isoformat()

        response = self.client.post("/workouts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": 1})

        response = self.client.get(
            "/workouts", params={"sort_by": "id", "descending": True}
        )
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
            response.json(),
            [
                {
                    "id": 1,
                    "name": "Bench Press",
                    "equipment": "Olympic Barbell",
                    "note": None,
                }
            ],
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
            response.json(),
            [
                {
                    "id": 1,
                    "reps": 10,
                    "weight": 100.0,
                    "rpe": 8,
                    "warmup": False,
                    "position": 1,
                }
            ],
        )

        response = self.client.put(
            "/sets/1", params={"reps": 12, "weight": 105.0, "rpe": 9}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "updated"})

        response = self.client.get("/exercises/1/sets")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "id": 1,
                    "reps": 12,
                    "weight": 105.0,
                    "rpe": 9,
                    "warmup": False,
                    "position": 1,
                }
            ],
        )

        response = self.client.get("/workouts/1/export_csv")
        self.assertEqual(response.status_code, 200)
        csv_text = response.text.strip().splitlines()
        self.assertEqual(csv_text[0], "Exercise,Equipment,Reps,Weight,RPE,Start,End")
        self.assertIn("Bench Press", csv_text[1])

        response = self.client.get("/workouts/1/export_json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["exercise"], "Bench Press")

        response = self.client.get("/workouts/1/export_xml")
        self.assertEqual(response.status_code, 200)
        self.assertIn("<workout", response.text)

        response = self.client.delete("/sets/1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "deleted"})

        response = self.client.get("/exercises/1/sets")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_create_workout_with_timezone(self) -> None:
        resp = self.client.post(
            "/workouts",
            params={"timezone": "America/New_York"},
        )
        self.assertEqual(resp.status_code, 200)
        wid = resp.json()["id"]
        resp = self.client.get(f"/workouts/{wid}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["timezone"], "America/New_York")

        response = self.client.delete("/exercises/1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "deleted"})

        response = self.client.get("/workouts/1/exercises")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_workout_icon(self) -> None:
        resp = self.client.post("/workouts", params={"icon": "🔥"})
        self.assertEqual(resp.status_code, 200)
        wid = resp.json()["id"]
        resp = self.client.get(f"/workouts/{wid}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["icon"], "🔥")
        resp = self.client.put(f"/workouts/{wid}/icon", params={"icon": "💧"})
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get(f"/workouts/{wid}")
        self.assertEqual(resp.json()["icon"], "💧")

        response = self.client.delete("/workouts/1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "deleted"})

        response = self.client.get("/workouts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_workout_sorting(self) -> None:
        d1 = "2024-01-01"
        d2 = "2024-01-02"
        self.client.post("/workouts", params={"date": d2})
        self.client.post("/workouts", params={"date": d1})
        resp = self.client.get(
            "/workouts",
            params={"sort_by": "date", "descending": False},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data[0]["date"], d1)
        self.assertEqual(data[1]["date"], d2)

    def test_workout_pagination(self) -> None:
        dates = ["2024-01-01", "2024-01-02", "2024-01-03"]
        for d in dates:
            self.client.post("/workouts", params={"date": d})
        resp = self.client.get(
            "/workouts",
            params={"sort_by": "id", "descending": False, "limit": 2, "offset": 0},
        )
        self.assertEqual(len(resp.json()), 2)
        resp2 = self.client.get(
            "/workouts",
            params={"sort_by": "id", "descending": False, "limit": 2, "offset": 2},
        )
        self.assertEqual(len(resp2.json()), 1)
        self.assertEqual(resp2.json()[0]["date"], dates[2])

    def test_weekly_planner_endpoint(self) -> None:
        today = datetime.date.today()
        for i in range(3):
            d = (today + datetime.timedelta(days=i)).isoformat()
            self.client.post("/planned_workouts", params={"date": d})
        resp = self.client.get("/planned_workouts/weekly")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 3)

    def test_delete_endpoints(self) -> None:
        plan_date = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

        d = "2024-01-01"
        self.client.post("/workouts", params={"date": d})
        self.client.post(
            "/planned_workouts",
            params={"date": plan_date, "training_type": "strength"},
        )

        response = self.client.post(
            "/settings/delete_all", params={"confirmation": "Yes, I confirm"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "deleted"})

        response = self.client.get("/workouts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

        response = self.client.get("/planned_workouts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

        d = "2024-01-01"
        self.client.post("/workouts", params={"date": d})
        self.client.post(
            "/planned_workouts",
            params={"date": plan_date, "training_type": "strength"},
        )

        response = self.client.post(
            "/settings/delete_logged", params={"confirmation": "Yes, I confirm"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "deleted"})

        response = self.client.get("/workouts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

        response = self.client.get("/planned_workouts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

        response = self.client.post(
            "/settings/delete_planned", params={"confirmation": "Yes, I confirm"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "deleted"})

        response = self.client.get("/planned_workouts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_general_settings(self) -> None:
        resp = self.client.get("/settings/general")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["body_weight"], 80.0)
        self.assertEqual(data["height"], 1.75)
        self.assertEqual(data["months_active"], 1.0)
        self.assertEqual(data["theme"], "light")
        self.assertEqual(data["timezone"], "UTC")
        self.assertFalse(data["compact_mode"])
        self.assertFalse(data["auto_dark_mode"])
        self.assertFalse(data["show_onboarding"])
        self.assertFalse(data["show_help_tips"])
        self.assertFalse(data["auto_open_last_workout"])
        self.assertFalse(data["game_enabled"])
        self.assertIn("ml_all_enabled", data)
        self.assertEqual(data["accent_color"], "#ff4b4b")

        resp = self.client.post(
            "/settings/general",
            params={
                "body_weight": 85.5,
                "height": 1.8,
                "months_active": 6.0,
                "theme": "dark",
                "timezone": "America/New_York",
                "quick_weight_increment": 1.0,
                "ml_all_enabled": False,
                "compact_mode": True,
                "auto_dark_mode": True,
                "show_onboarding": True,
                "show_help_tips": True,
                "auto_open_last_workout": True,
                "accent_color": "#00ff00",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "updated"})

        with open(self.yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self.assertEqual(float(data["body_weight"]), 85.5)
        self.assertEqual(float(data["height"]), 1.8)
        self.assertEqual(float(data["months_active"]), 6.0)
        self.assertEqual(data["theme"], "dark")
        self.assertEqual(data["auto_dark_mode"], True)
        self.assertTrue(data["show_onboarding"])
        self.assertTrue(data["show_help_tips"])
        self.assertTrue(data["auto_open_last_workout"])
        self.assertEqual(data["timezone"], "America/New_York")
        self.assertEqual(float(data["quick_weight_increment"]), 1.0)
        self.assertEqual(data["accent_color"], "#00ff00")

    def test_timezone_setting(self) -> None:
        resp = self.client.post(
            "/settings/general",
            params={"timezone": "Asia/Tokyo"},
        )
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get("/settings/general")
        self.assertEqual(resp.json()["timezone"], "Asia/Tokyo")
        new_data = {
            "body_weight": 90.0,
            "height": 1.7,
            "months_active": 12.0,
            "theme": "light",
            "timezone": "UTC",
            "game_enabled": "0",
            "ml_all_enabled": "0",
            "compact_mode": "1",
            "auto_dark_mode": "1",
            "show_onboarding": "1",
            "show_help_tips": "1",
            "auto_open_last_workout": "1",
        }
        with open(self.yaml_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(new_data, f)

        resp = self.client.get("/settings/general")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["body_weight"], 90.0)
        self.assertEqual(data["height"], 1.7)
        self.assertEqual(data["months_active"], 12.0)
        self.assertEqual(data["theme"], "light")
        self.assertEqual(data["timezone"], "UTC")
        self.assertFalse(data["game_enabled"])
        self.assertFalse(data["ml_all_enabled"])
        self.assertTrue(data["compact_mode"])
        self.assertTrue(data["auto_dark_mode"])
        self.assertTrue(data["show_onboarding"])
        self.assertTrue(data["show_help_tips"])
        self.assertTrue(data["auto_open_last_workout"])

    def test_ml_toggle(self) -> None:
        resp = self.client.post("/settings/general", params={"ml_all_enabled": False})
        self.assertEqual(resp.status_code, 200)
        self.client.post("/workouts")
        self.client.post(
            "/exercise_names/link",
            params={"name1": "Barbell Bench Press", "name2": "Bench Press"},
        )
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM ml_models;")
        count = cur.fetchone()[0]
        conn.close()
        self.assertEqual(count, 0)

    def test_hide_preconfigured_equipment(self) -> None:
        resp = self.client.get("/equipment")
        self.assertIn("Olympic Barbell", resp.json())

        resp = self.client.post(
            "/settings/general", params={"hide_preconfigured_equipment": True}
        )
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get("/equipment/types")
        # Equipment types must remain visible even when preconfigured equipment
        # is hidden. The toggle should only affect individual equipment items.
        self.assertIn("Free Weights", resp.json())
        resp = self.client.get("/equipment")
        self.assertNotIn("Olympic Barbell", resp.json())

        resp = self.client.post(
            "/settings/general", params={"hide_preconfigured_equipment": False}
        )
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get("/equipment")
        self.assertIn("Olympic Barbell", resp.json())

    def test_hide_preconfigured_exercises(self) -> None:
        resp = self.client.get(
            "/exercise_catalog",
            params={"muscle_groups": "Chest"},
        )
        self.assertIn("Barbell Bench Press", resp.json())

        resp = self.client.post(
            "/settings/general", params={"hide_preconfigured_exercises": True}
        )
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get(
            "/exercise_catalog",
            params={"muscle_groups": "Chest"},
        )
        self.assertNotIn("Barbell Bench Press", resp.json())

        resp = self.client.post(
            "/settings/general", params={"hide_preconfigured_exercises": False}
        )
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get(
            "/exercise_catalog",
            params={"muscle_groups": "Chest"},
        )
        self.assertIn("Barbell Bench Press", resp.json())

    def test_rpe_scale_setting(self) -> None:
        resp = self.client.post("/settings/general", params={"rpe_scale": 5})
        self.assertEqual(resp.status_code, 200)
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        ok = self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 5},
        )
        self.assertEqual(ok.status_code, 200)
        bad = self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 6},
        )
        self.assertEqual(bad.status_code, 400)

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

        response = self.client.post(
            "/planned_exercises/1/sets", params={"reps": 5, "weight": 150.0, "rpe": 8}
        )
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
            [
                {
                    "id": 1,
                    "name": "Squat",
                    "equipment": "Olympic Barbell",
                    "note": None,
                }
            ],
        )

        response = self.client.get("/exercises/1/sets")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "id": 1,
                    "reps": 5,
                    "weight": 150.0,
                    "rpe": 8,
                    "warmup": False,
                    "position": 1,
                }
            ],
        )

        response = self.client.put(
            "/sets/1", params={"reps": 6, "weight": 160.0, "rpe": 9}
        )
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
                "note": None,
                "warmup": False,
                "velocity": 0.0,
                "position": 1,
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

        add_type = self.client.post("/equipment/types", params={"name": "MyType"})
        self.assertEqual(add_type.status_code, 200)
        self.assertIsInstance(add_type.json()["id"], int)
        self.assertIn("MyType", self.client.get("/equipment/types").json())

        dup = self.client.post("/equipment/types", params={"name": "mytype"})
        self.assertEqual(dup.status_code, 400)

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
            "/workouts/1/exercises",
            params={"name": "Clean", "equipment": "Olympic Barbell"},
        )
        resp = self.client.get("/workouts/1/exercises")
        self.assertEqual(
            resp.json(),
            [
                {
                    "id": 1,
                    "name": "Clean",
                    "equipment": "Olympic Barbell",
                    "note": None,
                }
            ],
        )

        # custom equipment lifecycle
        resp = self.client.post(
            "/equipment",
            params={
                "equipment_type": "MyType",
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
                "equipment_type": "MyType",
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

    def test_bulk_sets_endpoint(self) -> None:
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        resp = self.client.post(
            "/exercises/1/bulk_sets",
            params={"sets": "5,100,8|5,105,9"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"added": 2})
        data = self.client.get("/exercises/1/sets").json()
        self.assertEqual(len(data), 2)

    def test_set_reordering(self) -> None:
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        for r in [(5, 100.0, 8), (6, 105.0, 9), (4, 95.0, 7)]:
            self.client.post(
                "/exercises/1/sets",
                params={"reps": r[0], "weight": r[1], "rpe": r[2]},
            )
        resp = self.client.post(
            "/exercises/1/set_order",
            params={"order": "3,1,2"},
        )
        self.assertEqual(resp.status_code, 200)
        sets = self.client.get("/exercises/1/sets").json()
        ids = [s["id"] for s in sets]
        self.assertEqual(ids, [3, 1, 2])

    def test_invalid_set_values(self) -> None:
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        resp = self.client.post(
            "/exercises/1/sets",
            params={"reps": -1, "weight": 100.0, "rpe": 8},
        )
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
                    position INTEGER NOT NULL,
                    FOREIGN KEY(exercise_id) REFERENCES exercises(id) ON DELETE CASCADE
                );"""
        )
        cur.execute(
            """CREATE TABLE workout_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    training_type TEXT NOT NULL DEFAULT 'strength'
                );"""
        )
        cur.execute(
            "INSERT INTO workout_templates (name, training_type) VALUES ('Legacy Template','strength');"
        )
        today = datetime.date.today().isoformat()
        cur.execute("INSERT INTO workouts (date) VALUES (?);", (today,))
        cur.execute("INSERT INTO exercises (workout_id, name) VALUES (1, 'Legacy Ex');")
        cur.execute(
            "INSERT INTO sets (exercise_id, reps, weight, rpe, position) VALUES (1, 8, 80.0, 7, 1);"
        )
        conn.commit()
        conn.close()

        api = GymAPI(db_path=self.db_path)
        client = TestClient(api.app)

        resp = client.get("/exercises/1/sets")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json(),
            [
                {
                    "id": 1,
                    "reps": 8,
                    "weight": 80.0,
                    "rpe": 7,
                    "warmup": False,
                    "position": 1,
                }
            ],
        )

        resp = client.get("/sets/1")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("planned_set_id", data)
        self.assertIn("diff_reps", data)

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(workout_templates);")
        cols = [r[1] for r in cur.fetchall()]
        self.assertIn("position", cols)
        conn.close()

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

        resp = self.client.get("/gamification/workout_points")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["workout_id"], 1)
        self.assertAlmostEqual(data[0]["points"], 101.31, places=2)

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

    def test_add_muscle(self) -> None:
        resp = self.client.post("/muscles", params={"name": "Obliques"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "added"})

        resp = self.client.get("/muscles")
        self.assertIn("Obliques", resp.json())

        resp_dup = self.client.post("/muscles", params={"name": "Obliques"})
        self.assertEqual(resp_dup.status_code, 400)

    def test_muscle_alias(self) -> None:
        resp = self.client.get("/muscles")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Biceps Brachii", resp.json())

        resp = self.client.post(
            "/muscles/alias",
            params={"new_name": "My Biceps", "existing": "Biceps Brachii"},
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.client.post(
            "/muscles/link", params={"name1": "My Biceps", "name2": "Brachialis"}
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get("/equipment", params={"muscles": "My Biceps"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("EZ Curl Bar", resp.json())

        resp = self.client.get("/exercise_catalog", params={"muscles": "My Biceps"})
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

        del_resp = self.client.delete("/exercise_names/alias/My Pulls")
        self.assertEqual(del_resp.status_code, 200)
        names = self.client.get("/exercise_names").json()
        self.assertNotIn("My Pulls", names)

    def test_exercise_variants(self) -> None:
        self.client.post(
            "/exercise_variants/link",
            params={"name": "Barbell Bench Press", "variant": "Dumbbell Bench Press"},
        )

        resp = self.client.get("/exercise_variants/Barbell Bench Press")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Dumbbell Bench Press", resp.json())

        resp = self.client.delete(
            "/exercise_variants/link",
            params={"name": "Barbell Bench Press", "variant": "Dumbbell Bench Press"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "unlinked"})

        resp = self.client.get("/exercise_variants/Barbell Bench Press")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("Dumbbell Bench Press", resp.json())

    def test_statistics_endpoints(self) -> None:
        self.client.post("/workouts")
        today = datetime.date.today().isoformat()
        self.client.post(
            "/exercise_names/link",
            params={"name1": "Barbell Bench Press", "name2": "Bench Press"},
        )
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

        resp = self.client.get("/stats/muscle_usage")
        self.assertEqual(resp.status_code, 200)
        mus_stats = resp.json()
        target = next((m for m in mus_stats if m["muscle"] == "Pectoralis Major"), None)
        self.assertIsNotNone(target)
        self.assertEqual(target["sets"], 2)
        self.assertAlmostEqual(target["volume"], 1880.0)

        resp = self.client.get("/stats/muscle_group_usage")
        self.assertEqual(resp.status_code, 200)
        grp_stats = resp.json()
        chest = next((g for g in grp_stats if g["muscle_group"] == "Chest"), None)
        self.assertIsNotNone(chest)
        self.assertEqual(chest["sets"], 2)
        self.assertAlmostEqual(chest["volume"], 1880.0)

        resp = self.client.get(
            "/stats/daily_muscle_group_volume",
            params={"muscle_group": "Chest"},
        )
        self.assertEqual(resp.status_code, 200)
        mg_daily = resp.json()
        self.assertEqual(len(mg_daily), 1)
        self.assertEqual(mg_daily[0]["date"], today)
        self.assertAlmostEqual(mg_daily[0]["volume"], 1880.0)
        self.assertEqual(mg_daily[0]["sets"], 2)

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
            "/stats/intensity_distribution",
            params={"exercise": "Bench Press"},
        )
        self.assertEqual(resp.status_code, 200)
        intensity = resp.json()
        self.assertEqual(len(intensity), 11)
        zone = next((z for z in intensity if z["zone"] == "70-80"), None)
        self.assertIsNotNone(zone)
        self.assertEqual(zone["sets"], 2)
        self.assertAlmostEqual(zone["volume"], 1880.0)

        resp = self.client.get("/stats/muscle_engagement_3d")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(any(d["muscle"] == "Pectoralis Major" for d in data))

        resp = self.client.get(
            "/prediction/progress",
            params={"exercise": "Bench Press", "weeks": 2, "workouts": 1},
        )
        self.assertEqual(resp.status_code, 200)
        forecast = resp.json()
        self.assertEqual(len(forecast), 2)
        self.assertIn("est_1rm", forecast[0])
        self.assertIsInstance(forecast[0]["est_1rm"], float)

        resp = self.client.get("/stats/overview")
        self.assertEqual(resp.status_code, 200)
        overview = resp.json()
        self.assertEqual(overview["workouts"], 1)
        self.assertAlmostEqual(overview["volume"], 1880.0)
        self.assertAlmostEqual(overview["avg_rpe"], 8.5)
        self.assertEqual(overview["exercises"], 1)
        self.assertAlmostEqual(overview["avg_density"], 0.0)

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

        resp = self.client.get(
            "/stats/personal_record_history",
            params={"exercise": "Bench Press"},
        )
        self.assertEqual(resp.status_code, 200)
        history = resp.json()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["reps"], 10)
        self.assertAlmostEqual(history[0]["est_1rm"], 126.6, places=1)
        self.assertEqual(history[1]["reps"], 8)
        self.assertAlmostEqual(history[-1]["est_1rm"], 139.3, places=1)

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

    def test_workout_notes(self) -> None:
        resp = self.client.post(
            "/workouts",
            params={"training_type": "strength", "notes": "felt good"},
        )
        self.assertEqual(resp.status_code, 200)
        wid = resp.json()["id"]

        resp = self.client.get(f"/workouts/{wid}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["notes"], "felt good")

        resp = self.client.put(
            f"/workouts/{wid}/note",
            params={"notes": "tired"},
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get(f"/workouts/{wid}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["notes"], "tired")

    def test_workout_location(self) -> None:
        resp = self.client.post(
            "/workouts",
            params={"training_type": "strength", "location": "Home"},
        )
        self.assertEqual(resp.status_code, 200)
        wid = resp.json()["id"]

        resp = self.client.get(f"/workouts/{wid}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["location"], "Home")

        resp = self.client.put(
            f"/workouts/{wid}/location",
            params={"location": "Gym"},
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get(f"/workouts/{wid}")
        self.assertEqual(resp.json()["location"], "Gym")

    def test_workout_comments(self) -> None:
        resp = self.client.post("/workouts")
        wid = resp.json()["id"]
        resp = self.client.post(
            f"/workouts/{wid}/comments",
            params={"comment": "Great", "timestamp": "2024-01-01T10:00:00"},
        )
        self.assertEqual(resp.status_code, 200)
        cid = resp.json()["id"]
        resp = self.client.get(f"/workouts/{wid}/comments")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json(),
            [{"id": cid, "timestamp": "2024-01-01T10:00:00", "comment": "Great"}],
        )

    def test_workout_rating(self) -> None:
        resp = self.client.post(
            "/workouts",
            params={"training_type": "strength", "rating": 4},
        )
        self.assertEqual(resp.status_code, 200)
        wid = resp.json()["id"]

        resp = self.client.get(f"/workouts/{wid}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["rating"], 4)

        resp = self.client.put(
            f"/workouts/{wid}/rating",
            params={"rating": 5},
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get(f"/workouts/{wid}")
        self.assertEqual(resp.json()["rating"], 5)

    def test_workout_mood(self) -> None:
        resp = self.client.post(
            "/workouts",
            params={"training_type": "strength", "mood_before": 3},
        )
        wid = resp.json()["id"]
        self.assertEqual(
            self.client.get(f"/workouts/{wid}").json()["mood_before"], 3
        )
        self.client.put(f"/workouts/{wid}/mood_after", params={"mood": 4})
        self.assertEqual(
            self.client.get(f"/workouts/{wid}").json()["mood_after"], 4
        )

    def test_websocket_updates(self) -> None:
        with self.client.websocket_connect("/ws/updates") as ws:
            self.client.post("/workouts")
            data = ws.receive_json()
            self.assertEqual(data["type"], "workout_added")

    def test_set_notes(self) -> None:
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        resp = self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8, "note": "tough"},
        )
        self.assertEqual(resp.status_code, 200)
        set_id = resp.json()["id"]
        data = self.client.get(f"/sets/{set_id}").json()
        self.assertEqual(data["note"], "tough")
        upd = self.client.put(f"/sets/{set_id}/note", params={"note": "easy"})
        self.assertEqual(upd.status_code, 200)
        data = self.client.get(f"/sets/{set_id}").json()
        self.assertEqual(data["note"], "easy")

    def test_bulk_update_sets(self) -> None:
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 6, "weight": 105.0, "rpe": 8},
        )
        self.client.post("/workouts")
        self.client.post(
            "/workouts/2/exercises",
            params={"name": "Squat", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/2/sets",
            params={"reps": 8, "weight": 150.0, "rpe": 7},
        )
        updates = [
            {"id": 1, "reps": 5, "weight": 110.0, "rpe": 9},
            {"id": 3, "reps": 10, "weight": 160.0, "rpe": 8},
        ]
        resp = self.client.put("/sets/bulk_update", json=updates)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"updated": 2})
        set1 = self.client.get("/sets/1").json()
        set3 = self.client.get("/sets/3").json()
        self.assertEqual(set1["weight"], 110.0)
        self.assertEqual(set3["reps"], 10)

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
        self.client.post(
            "/workouts", params={"date": d2, "training_type": "hypertrophy"}
        )
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

        paged = self.client.get(
            "/workouts/history",
            params={"start_date": d1, "end_date": d2, "limit": 1, "offset": 0},
        )
        self.assertEqual(paged.status_code, 200)
        self.assertEqual(len(paged.json()), 1)
        paged2 = self.client.get(
            "/workouts/history",
            params={"start_date": d1, "end_date": d2, "limit": 1, "offset": 1},
        )
        self.assertEqual(len(paged2.json()), 1)

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
            params={
                "weights": "130|120",
                "starting_weight": 100.0,
                "max_achieved": 90.0,
            },
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

    def test_training_stress_endpoint(self) -> None:
        d1 = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        d2 = datetime.date.today().isoformat()

        self.client.post("/workouts", params={"date": d1})
        self.client.post("/workouts", params={"date": d2})

        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/workouts/2/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )

        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        self.client.post(
            "/exercises/2/sets",
            params={"reps": 5, "weight": 110.0, "rpe": 8},
        )

        resp = self.client.get(
            "/stats/training_stress",
            params={"start_date": d1, "end_date": d2},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["date"], d1)
        self.assertAlmostEqual(data[0]["stress"], 1.02, places=2)
        self.assertAlmostEqual(data[0]["fatigue"], 1.02, places=2)
        self.assertEqual(data[1]["date"], d2)
        self.assertAlmostEqual(data[1]["stress"], 1.02, places=2)
        self.assertAlmostEqual(data[1]["fatigue"], 1.78, places=2)

    def test_load_variability_endpoint(self) -> None:
        d1 = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
        d2 = datetime.date.today().isoformat()

        self.client.post("/workouts", params={"date": d1})
        self.client.post("/workouts", params={"date": d2})

        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/workouts/2/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )

        self.client.post(
            "/exercises/1/sets",
            params={"reps": 10, "weight": 100.0, "rpe": 8},
        )
        self.client.post(
            "/exercises/2/sets",
            params={"reps": 10, "weight": 150.0, "rpe": 8},
        )

        resp = self.client.get(
            "/stats/load_variability",
            params={"start_date": d1, "end_date": d2},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertAlmostEqual(data["variability"], 0.2, places=2)
        self.assertEqual(len(data["weeks"]), 2)

    def test_training_monotony_endpoint(self) -> None:
        d1 = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
        d2 = datetime.date.today().isoformat()

        self.client.post("/workouts", params={"date": d1})
        self.client.post("/workouts", params={"date": d2})

        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/workouts/2/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )

        self.client.post(
            "/exercises/1/sets",
            params={"reps": 10, "weight": 100.0, "rpe": 8},
        )
        self.client.post(
            "/exercises/2/sets",
            params={"reps": 10, "weight": 150.0, "rpe": 8},
        )

        resp = self.client.get(
            "/stats/training_monotony",
            params={"start_date": d1, "end_date": d2},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertAlmostEqual(data["monotony"], 5.0, places=2)

    def test_stress_balance_endpoint(self) -> None:
        d1 = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        d2 = datetime.date.today().isoformat()

        self.client.post("/workouts", params={"date": d1})
        self.client.post("/workouts", params={"date": d2})

        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/workouts/2/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )

        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        self.client.post(
            "/exercises/2/sets",
            params={"reps": 5, "weight": 110.0, "rpe": 8},
        )

        resp = self.client.get(
            "/stats/stress_balance",
            params={"start_date": d1, "end_date": d2},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["tsb"], 0.0)
        self.assertEqual(data[1]["tsb"], 0.0)

    def test_stress_overview_endpoint(self) -> None:
        d1 = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        d2 = datetime.date.today().isoformat()

        self.client.post("/workouts", params={"date": d1})
        self.client.post("/workouts", params={"date": d2})

        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/workouts/2/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )

        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        self.client.post(
            "/exercises/2/sets",
            params={"reps": 5, "weight": 110.0, "rpe": 8},
        )

        resp = self.client.get(
            "/stats/stress_overview",
            params={"start_date": d1, "end_date": d2},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertAlmostEqual(data["stress"], 2.0, places=2)
        self.assertAlmostEqual(data["fatigue"], 1.78, places=2)

    def test_session_efficiency_endpoint(self) -> None:
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        resp = self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        set_id = resp.json()["id"]
        start_resp = self.client.post(f"/sets/{set_id}/start")
        end_resp = self.client.post(f"/sets/{set_id}/finish")
        self.assertEqual(start_resp.status_code, 200)
        self.assertEqual(end_resp.status_code, 200)
        set_data = self.client.get(f"/sets/{set_id}").json()
        t0 = datetime.datetime.fromisoformat(set_data["start_time"])
        t1 = datetime.datetime.fromisoformat(set_data["end_time"])
        duration = (t1 - t0).total_seconds()
        expected = MathTools.session_efficiency(500.0, duration, 8)
        resp = self.client.get("/stats/session_efficiency")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["workout_id"], 1)
        self.assertAlmostEqual(data[0]["efficiency"], round(expected, 2), places=2)

    def test_session_density_endpoint(self) -> None:
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        resp = self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        set_id = resp.json()["id"]
        self.client.post(f"/sets/{set_id}/start")
        self.client.post(f"/sets/{set_id}/finish")
        data = self.client.get(f"/sets/{set_id}").json()
        t0 = datetime.datetime.fromisoformat(data["start_time"])
        t1 = datetime.datetime.fromisoformat(data["end_time"])
        duration = (t1 - t0).total_seconds()
        expected = MathTools.session_density(500.0, duration)
        resp = self.client.get("/stats/session_density")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["workout_id"], 1)
        self.assertAlmostEqual(data[0]["density"], round(expected, 2), places=2)

    def test_set_pace_endpoint(self) -> None:
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        sid = self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        ).json()["id"]
        self.client.post(f"/sets/{sid}/start")
        self.client.post(f"/sets/{sid}/finish")
        data = self.client.get(f"/sets/{sid}").json()
        t0 = datetime.datetime.fromisoformat(data["start_time"])
        t1 = datetime.datetime.fromisoformat(data["end_time"])
        duration = (t1 - t0).total_seconds()
        expected = MathTools.set_pace(1, duration)
        resp = self.client.get("/stats/set_pace")
        self.assertEqual(resp.status_code, 200)
        out = resp.json()
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["workout_id"], 1)
        self.assertAlmostEqual(out[0]["pace"], round(expected, 2), places=2)

    def test_rest_times_endpoint(self) -> None:
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        ids = []
        for _ in range(2):
            resp = self.client.post(
                "/exercises/1/sets",
                params={"reps": 5, "weight": 100.0, "rpe": 8},
            )
            ids.append(resp.json()["id"])
        t0 = datetime.datetime(2023, 1, 1, 0, 0, 0)
        self.client.post(
            f"/sets/{ids[0]}/start",
            params={"timestamp": t0.isoformat()},
        )
        self.client.post(
            f"/sets/{ids[0]}/finish",
            params={"timestamp": (t0 + datetime.timedelta(seconds=10)).isoformat()},
        )
        self.client.post(
            f"/sets/{ids[1]}/start",
            params={"timestamp": (t0 + datetime.timedelta(seconds=70)).isoformat()},
        )
        self.client.post(
            f"/sets/{ids[1]}/finish",
            params={"timestamp": (t0 + datetime.timedelta(seconds=80)).isoformat()},
        )
        resp = self.client.get("/stats/rest_times")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["workout_id"], 1)
        self.assertAlmostEqual(data[0]["avg_rest"], 60.0, places=2)

    def test_session_duration_endpoint(self) -> None:
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        ids = []
        for _ in range(2):
            resp = self.client.post(
                "/exercises/1/sets",
                params={"reps": 5, "weight": 100.0, "rpe": 8},
            )
            ids.append(resp.json()["id"])
        t0 = datetime.datetime(2023, 1, 1, 0, 0, 0)
        self.client.post(
            f"/sets/{ids[0]}/start",
            params={"timestamp": t0.isoformat()},
        )
        self.client.post(
            f"/sets/{ids[0]}/finish",
            params={"timestamp": (t0 + datetime.timedelta(seconds=10)).isoformat()},
        )
        self.client.post(
            f"/sets/{ids[1]}/start",
            params={"timestamp": (t0 + datetime.timedelta(seconds=70)).isoformat()},
        )
        self.client.post(
            f"/sets/{ids[1]}/finish",
            params={"timestamp": (t0 + datetime.timedelta(seconds=80)).isoformat()},
        )
        resp = self.client.get("/stats/session_duration")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["workout_id"], 1)
        self.assertAlmostEqual(data[0]["duration"], 80.0, places=2)

    def test_time_under_tension_endpoint(self) -> None:
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        ids = []
        for i in range(2):
            resp = self.client.post(
                "/exercises/1/sets",
                params={"reps": 5, "weight": 100.0, "rpe": 8},
            )
            ids.append(resp.json()["id"])
            start = datetime.datetime(2023, 1, 1, 0, 0, i * 10)
            end = start + datetime.timedelta(seconds=5)
            self.client.post(
                f"/sets/{ids[i]}/start",
                params={"timestamp": start.isoformat()},
            )
            self.client.post(
                f"/sets/{ids[i]}/finish",
                params={"timestamp": end.isoformat()},
            )
        resp = self.client.get("/stats/time_under_tension")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["workout_id"], 1)
        self.assertAlmostEqual(data[0]["tut"], 10.0, places=2)

    def test_exercise_diversity_endpoint(self) -> None:
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Squat", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/1/sets", params={"reps": 5, "weight": 100.0, "rpe": 8}
        )
        self.client.post(
            "/exercises/2/sets", params={"reps": 5, "weight": 100.0, "rpe": 8}
        )
        resp = self.client.get("/stats/exercise_diversity")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["workout_id"], 1)
        self.assertAlmostEqual(data[0]["diversity"], 1.0, places=2)

    def test_location_summary_endpoint(self) -> None:
        self.client.post(
            "/workouts",
            params={"date": "2023-01-01", "location": "Home"},
        )
        self.client.post(
            "/workouts",
            params={"date": "2023-01-02", "location": "Gym"},
        )
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/workouts/2/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        self.client.post(
            "/exercises/2/sets",
            params={"reps": 5, "weight": 110.0, "rpe": 8},
        )
        resp = self.client.get("/stats/location_summary")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["location"], "Gym")
        self.assertEqual(data[0]["workouts"], 1)
        self.assertAlmostEqual(data[0]["volume"], 550.0)
        self.assertEqual(data[1]["location"], "Home")
        self.assertEqual(data[1]["workouts"], 1)
        self.assertAlmostEqual(data[1]["volume"], 500.0)

    def test_training_type_summary_endpoint(self) -> None:
        self.client.post(
            "/workouts",
            params={"date": "2023-01-01", "training_type": "strength"},
        )
        self.client.post(
            "/workouts",
            params={"date": "2023-01-02", "training_type": "hypertrophy"},
        )
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/workouts/2/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        self.client.post(
            "/exercises/2/sets",
            params={"reps": 5, "weight": 110.0, "rpe": 8},
        )
        resp = self.client.get("/stats/training_type_summary")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["training_type"], "hypertrophy")
        self.assertEqual(data[0]["workouts"], 1)
        self.assertAlmostEqual(data[0]["volume"], 550.0)
        self.assertEqual(data[0]["sets"], 1)
        self.assertEqual(data[1]["training_type"], "strength")
        self.assertEqual(data[1]["workouts"], 1)
        self.assertAlmostEqual(data[1]["volume"], 500.0)
        self.assertEqual(data[1]["sets"], 1)

    def test_weekly_volume_change_endpoint(self) -> None:
        d1 = (datetime.date.today() - datetime.timedelta(days=14)).isoformat()
        d2 = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()

        self.client.post("/workouts", params={"date": d1})
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 10, "weight": 100.0, "rpe": 8},
        )

        self.client.post("/workouts", params={"date": d2})
        self.client.post(
            "/workouts/2/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/2/sets",
            params={"reps": 20, "weight": 100.0, "rpe": 8},
        )

        resp = self.client.get(
            "/stats/weekly_volume_change",
            params={"start_date": d1, "end_date": d2},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["week"], d2)
        self.assertAlmostEqual(data[0]["change"], 100.0, places=2)

    def test_weekly_streak_endpoint(self) -> None:
        dates = [
            "2024-01-01",
            "2024-01-08",
            "2024-01-15",
            "2024-02-05",
        ]
        for d in dates:
            self.client.post("/workouts", params={"date": d})
        resp = self.client.get("/stats/weekly_streak")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["current"], 1)
        self.assertEqual(data["best"], 3)

    def test_set_velocity_and_history(self) -> None:
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        resp = self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        set_id = resp.json()["id"]
        start = "2023-01-01T00:00:00"
        end = "2023-01-01T00:00:05"
        self.client.post(f"/sets/{set_id}/start", params={"timestamp": start})
        self.client.post(f"/sets/{set_id}/finish", params={"timestamp": end})

        resp = self.client.get(f"/sets/{set_id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("velocity", data)
        self.assertAlmostEqual(data["velocity"], 0.5, places=2)

        resp = self.client.get(
            "/stats/exercise_history",
            params={"exercise": "Bench Press"},
        )
        self.assertEqual(resp.status_code, 200)
        history = resp.json()
        self.assertAlmostEqual(history[0]["velocity"], 0.5, places=2)

    def test_velocity_history_endpoint(self) -> None:
        today = datetime.date.today().isoformat()
        self.client.post("/workouts", params={"date": today})
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        for i in range(2):
            resp = self.client.post(
                "/exercises/1/sets",
                params={"reps": 5, "weight": 100.0, "rpe": 8},
            )
            set_id = resp.json()["id"]
            start = f"2023-01-01T00:00:{i*5:02d}"
            end = f"2023-01-01T00:00:{i*5+5:02d}"
            self.client.post(f"/sets/{set_id}/start", params={"timestamp": start})
            self.client.post(f"/sets/{set_id}/finish", params={"timestamp": end})

        resp = self.client.get(
            "/stats/velocity_history",
            params={"exercise": "Bench Press"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["date"], today)
        self.assertAlmostEqual(data[0]["velocity"], 0.5, places=2)

    def test_power_history_endpoint(self) -> None:
        today = datetime.date.today().isoformat()
        self.client.post("/workouts", params={"date": today})
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        for i in range(2):
            resp = self.client.post(
                "/exercises/1/sets",
                params={"reps": 5, "weight": 100.0, "rpe": 8},
            )
            set_id = resp.json()["id"]
            start = f"2023-01-01T00:00:{i*5:02d}"
            end = f"2023-01-01T00:00:{i*5+5:02d}"
            self.client.post(f"/sets/{set_id}/start", params={"timestamp": start})
            self.client.post(f"/sets/{set_id}/finish", params={"timestamp": end})

        resp = self.client.get(
            "/stats/power_history",
            params={"exercise": "Bench Press"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["date"], today)
        expected = MathTools.estimate_power_from_set(
            5, 100.0, "2023-01-01T00:00:00", "2023-01-01T00:00:05"
        )
        self.assertAlmostEqual(data[0]["power"], round(expected, 2), places=2)

    def test_relative_power_history_endpoint(self) -> None:
        today = datetime.date.today().isoformat()
        self.client.post("/workouts", params={"date": today})
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        for i in range(2):
            resp = self.client.post(
                "/exercises/1/sets",
                params={"reps": 5, "weight": 100.0, "rpe": 8},
            )
            set_id = resp.json()["id"]
            start = f"2023-01-01T00:00:{i*5:02d}"
            end = f"2023-01-01T00:00:{i*5+5:02d}"
            self.client.post(f"/sets/{set_id}/start", params={"timestamp": start})
            self.client.post(f"/sets/{set_id}/finish", params={"timestamp": end})

        resp = self.client.get(
            "/stats/relative_power_history",
            params={"exercise": "Bench Press"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["date"], today)
        expected = (
            MathTools.estimate_power_from_set(
                5, 100.0, "2023-01-01T00:00:00", "2023-01-01T00:00:05"
            )
            / 80.0
        )
        self.assertAlmostEqual(data[0]["relative_power"], round(expected, 2), places=2)

    def test_set_duration_endpoint(self) -> None:
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        set_id = self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        ).json()["id"]
        end = "2023-01-01T00:00:05"
        resp = self.client.post(
            f"/sets/{set_id}/duration", params={"seconds": 5, "end": end}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["end_time"], end)
        self.assertEqual(data["start_time"], "2023-01-01T00:00:00")
        resp = self.client.get(f"/sets/{set_id}")
        vel = resp.json()["velocity"]
        self.assertAlmostEqual(vel, 0.5, places=2)

    def test_volume_forecast_endpoint(self) -> None:
        d1 = (datetime.date.today() - datetime.timedelta(days=2)).isoformat()
        d2 = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        d3 = datetime.date.today().isoformat()

        self.client.post("/workouts", params={"date": d1})
        self.client.post("/workouts", params={"date": d2})
        self.client.post("/workouts", params={"date": d3})

        weights = [100.0, 110.0, 120.0]
        for wid, w in enumerate(weights, start=1):
            self.client.post(
                f"/workouts/{wid}/exercises",
                params={"name": "Bench Press", "equipment": "Olympic Barbell"},
            )
            self.client.post(
                "/exercises/{}/sets".format(wid),
                params={"reps": 5, "weight": w, "rpe": 8},
            )

        resp = self.client.get(
            "/stats/volume_forecast",
            params={"days": 2, "start_date": d1, "end_date": d3},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 2)
        self.assertIn("volume", data[0])
        self.assertIsInstance(data[0]["volume"], float)

    def test_muscle_progression_endpoint(self) -> None:
        today = datetime.date.today().isoformat()
        self.client.post("/workouts", params={"date": today})
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

        self.client.post(
            "/exercise_names/alias",
            params={"new_name": "Bench Press", "existing": "Barbell Bench Press"},
        )

        resp = self.client.get(
            "/stats/muscle_progression",
            params={"muscle": "Pectoralis Major"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["date"], today)
        expected = MathTools.epley_1rm(110.0, 8)
        self.assertAlmostEqual(data[0]["est_1rm"], round(expected, 2), places=2)

    def test_moving_average_progress_endpoint(self) -> None:
        d1 = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        d2 = datetime.date.today().isoformat()
        self.client.post("/workouts", params={"date": d1})
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        self.client.post("/workouts", params={"date": d2})
        self.client.post(
            "/workouts/2/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/2/sets",
            params={"reps": 5, "weight": 110.0, "rpe": 8},
        )

        resp = self.client.get(
            "/stats/moving_average_progress",
            params={"exercise": "Bench Press", "window": 2},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["date"], d1)
        expected1 = MathTools.epley_1rm(100.0, 5)
        self.assertAlmostEqual(data[0]["moving_avg"], round(expected1, 2), places=2)
        self.assertEqual(data[1]["date"], d2)
        expected2 = (MathTools.epley_1rm(100.0, 5) + MathTools.epley_1rm(110.0, 5)) / 2
        self.assertAlmostEqual(data[1]["moving_avg"], round(expected2, 2), places=2)

    def test_deload_recommendation_endpoint(self) -> None:
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 9},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 9},
        )

        resp = self.client.get(
            "/stats/deload_recommendation",
            params={"exercise": "Bench Press"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"trigger": 0.33, "score": 0.14})

    def test_overtraining_risk_endpoint(self) -> None:
        d1 = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        d2 = datetime.date.today().isoformat()

        self.client.post("/workouts", params={"date": d1})
        self.client.post("/workouts", params={"date": d2})

        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/workouts/2/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )

        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        self.client.post(
            "/exercises/2/sets",
            params={"reps": 5, "weight": 110.0, "rpe": 8},
        )

        overview = self.client.get(
            "/stats/stress_overview",
            params={"start_date": d1, "end_date": d2},
        ).json()
        variability = self.client.get(
            "/stats/load_variability",
            params={"start_date": d1, "end_date": d2},
        ).json()
        expected = MathTools.overtraining_index(
            overview["stress"], overview["fatigue"], variability["variability"]
        )

        resp = self.client.get(
            "/stats/overtraining_risk",
            params={"start_date": d1, "end_date": d2},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(resp.json()["risk"], round(expected, 2), places=2)

    def test_injury_risk_endpoint(self) -> None:
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )

        resp = self.client.get("/stats/injury_risk")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("injury_risk", data)
        self.assertGreaterEqual(data["injury_risk"], 0.0)
        self.assertLessEqual(data["injury_risk"], 1.0)

    def test_readiness_endpoint(self) -> None:
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        current_rm = ExercisePrescription._current_1rm([100.0], [5])
        stress = ExercisePrescription._stress_level(
            [100.0], [5], [8], [0], current_rm, 10
        )
        fatigue = ExercisePrescription._tss_adjusted_fatigue(
            [100.0], [5], [0], [50.0], current_rm
        )
        expected = MathTools.readiness_score(stress, fatigue / 1000)

        resp = self.client.get("/stats/readiness")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertIn("readiness", data[0])
        self.assertIsInstance(data[0]["readiness"], float)
        self.assertGreaterEqual(data[0]["readiness"], 0.0)

    def test_readiness_stats_endpoint(self) -> None:
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        resp = self.client.get("/stats/readiness_stats")
        self.assertEqual(resp.status_code, 200)
        stats = resp.json()
        self.assertIn("avg", stats)
        self.assertIn("min", stats)
        self.assertIn("max", stats)

    def test_adaptation_index_endpoint(self) -> None:
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )

        resp = self.client.get("/stats/adaptation_index")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("adaptation", data)
        self.assertIsInstance(data["adaptation"], float)
        self.assertGreaterEqual(data["adaptation"], 0.0)

    def test_performance_momentum_endpoint(self) -> None:
        d1 = (datetime.date.today() - datetime.timedelta(days=2)).isoformat()
        d2 = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        d3 = datetime.date.today().isoformat()

        self.client.post("/workouts", params={"date": d1})
        self.client.post("/workouts", params={"date": d2})
        self.client.post("/workouts", params={"date": d3})

        weights = [100.0, 105.0, 110.0]
        for wid, w in enumerate(weights, start=1):
            self.client.post(
                f"/workouts/{wid}/exercises",
                params={"name": "Bench Press", "equipment": "Olympic Barbell"},
            )
            self.client.post(
                f"/exercises/{wid}/sets",
                params={"reps": 5, "weight": w, "rpe": 8},
            )

        resp = self.client.get(
            "/stats/performance_momentum",
            params={"exercise": "Bench Press", "start_date": d1, "end_date": d3},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        base = datetime.date.fromisoformat(d1)
        times = [(datetime.date.fromisoformat(d) - base).days for d in [d1, d2, d3]]
        ests = [MathTools.epley_1rm(w, 5) for w in weights]
        slope = ExercisePrescription._weighted_slope(times, ests, alpha=0.4)
        change = ExercisePrescription._change_point(ests, times)
        low, mid, high = ExercisePrescription._wavelet_energy(ests)
        energy = high / (low + mid + ExercisePrescription.EPSILON)
        expected = slope * (1 + change / len(ests)) * (1 + energy / 10)
        self.assertAlmostEqual(data["momentum"], round(expected, 4), places=4)

    def test_training_strain_endpoint(self) -> None:
        start = (datetime.date.today() - datetime.timedelta(days=6)).isoformat()
        for i in range(7):
            date = (
                datetime.date.fromisoformat(start) + datetime.timedelta(days=i)
            ).isoformat()
            self.client.post("/workouts", params={"date": date})
            self.client.post(
                f"/workouts/{i + 1}/exercises",
                params={"name": "Bench Press", "equipment": "Olympic Barbell"},
            )
            self.client.post(
                f"/exercises/{i + 1}/sets",
                params={"reps": 5, "weight": 100.0, "rpe": 8},
            )

        end = datetime.date.fromisoformat(start) + datetime.timedelta(days=6)
        end_str = end.isoformat()
        resp = self.client.get(
            "/stats/training_strain",
            params={"start_date": start, "end_date": end_str},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)

        variability = self.client.get(
            "/stats/load_variability",
            params={"start_date": start, "end_date": end_str},
        ).json()["variability"]
        monotony = self.client.get(
            "/stats/training_monotony",
            params={"start_date": start, "end_date": end_str},
        ).json()["monotony"]
        expected = round(7 * 5 * 100.0 * monotony * (1 + variability / 10.0), 2)
        self.assertAlmostEqual(data[0]["strain"], expected, places=2)

    def test_plateau_score_endpoint(self) -> None:
        start = (datetime.date.today() - datetime.timedelta(days=5)).isoformat()
        for i in range(6):
            date = (
                datetime.date.fromisoformat(start) + datetime.timedelta(days=i)
            ).isoformat()
            self.client.post("/workouts", params={"date": date})
            self.client.post(
                f"/workouts/{i + 1}/exercises",
                params={"name": "Bench Press", "equipment": "Olympic Barbell"},
            )
            self.client.post(
                f"/exercises/{i + 1}/sets",
                params={"reps": 5, "weight": 100.0, "rpe": 8},
            )

        end = (
            datetime.date.fromisoformat(start) + datetime.timedelta(days=5)
        ).isoformat()
        resp = self.client.get(
            "/stats/advanced_plateau",
            params={"exercise": "Bench Press", "start_date": start, "end_date": end},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        perf = [MathTools.epley_1rm(100.0, 5) for _ in range(6)]
        times = list(range(6))
        rpes = [8] * 6
        vols = [500.0] * 6
        expected = ExercisePrescription._advanced_plateau_detection(
            perf, times, rpes, vols
        )
        self.assertAlmostEqual(data["score"], round(expected, 2), places=2)

    def test_warmup_weights_endpoint(self) -> None:
        resp = self.client.get(
            "/utils/warmup_weights",
            params={"target_weight": 100.0, "sets": 3},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"weights": [30.0, 60.0, 90.0]})

    def test_warmup_plan_endpoint(self) -> None:
        resp = self.client.get(
            "/utils/warmup_plan",
            params={"target_weight": 100.0, "target_reps": 5, "sets": 2},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json(),
            {"plan": [{"reps": 7, "weight": 30.0}, {"reps": 2, "weight": 90.0}]},
        )

    def test_add_warmup_sets(self) -> None:
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        resp = self.client.post(
            "/exercises/1/warmup_sets",
            params={"target_weight": 100.0, "target_reps": 5, "sets": 2},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["added"], 2)
        sets = self.client.get("/exercises/1/sets").json()
        self.assertEqual(len(sets), 2)
        self.assertTrue(all(s["warmup"] for s in sets))

    def test_ml_training(self) -> None:
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 105.0, "rpe": 8},
        )

        # trigger prediction to log confidence
        self.api.ml_service.predict("Bench Press", 5, 110.0, 8)

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT state FROM ml_models WHERE name = ?;", ("Bench Press",))
        row = cur.fetchone()
        conn.close()
        self.assertIsNotNone(row)
        import torch, io

        state = torch.load(io.BytesIO(row[0]))
        self.assertTrue(any(k.endswith("weight") for k in state))
        w_key = next(k for k in state if k.endswith("weight"))
        self.assertIsInstance(state[w_key], torch.Tensor)

        logs_resp = self.client.get("/ml_logs/Bench Press")
        self.assertEqual(logs_resp.status_code, 200)
        logs = logs_resp.json()
        self.assertGreaterEqual(len(logs), 1)
        first = logs[0]
        self.assertIsInstance(first["prediction"], float)
        self.assertIsInstance(first["confidence"], float)

        cv_resp = self.client.get(
            "/ml/cross_validate/performance_model", params={"folds": 2}
        )
        self.assertEqual(cv_resp.status_code, 200)
        self.assertIn("mse", cv_resp.json())

        # test date filtering
        ts_full = first["timestamp"]
        filtered = self.client.get(
            "/ml_logs/Bench Press",
            params={"start_date": ts_full, "end_date": ts_full},
        )
        self.assertEqual(filtered.status_code, 200)
        self.assertGreaterEqual(len(filtered.json()), 1)

        resp = self.client.post("/exercises/1/recommend_next")
        self.assertEqual(resp.status_code, 400)

    def test_body_weight_logging_and_stats(self) -> None:
        d1 = "2023-01-01"
        d2 = "2023-01-02"
        resp = self.client.post("/body_weight", params={"weight": 80.0, "date": d1})
        self.assertEqual(resp.status_code, 200)
        id1 = resp.json()["id"]
        resp = self.client.post("/body_weight", params={"weight": 82.0, "date": d2})
        self.assertEqual(resp.status_code, 200)
        id2 = resp.json()["id"]

        resp = self.client.get(
            "/body_weight", params={"start_date": d1, "end_date": d2}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["id"], id1)
        self.assertAlmostEqual(data[0]["weight"], 80.0)
        self.assertEqual(data[1]["id"], id2)
        self.assertAlmostEqual(data[1]["weight"], 82.0)

        resp = self.client.get(
            "/stats/weight_stats",
            params={"start_date": d1, "end_date": d2, "unit": "kg"},
        )
        self.assertEqual(resp.status_code, 200)
        stats = resp.json()
        self.assertAlmostEqual(stats["avg"], 81.0, places=2)
        self.assertEqual(stats["min"], 80.0)
        self.assertEqual(stats["max"], 82.0)
        cached = self.api.stats_cache.fetch_weight_stats(d1, d2, "kg")
        self.assertIsNotNone(cached)
        self.assertAlmostEqual(cached["avg"], 81.0, places=2)

        resp = self.client.get(
            "/stats/weight_stats",
            params={"start_date": d1, "end_date": d2, "unit": "lb"},
        )
        data_lb = resp.json()
        self.assertAlmostEqual(data_lb["avg"], 81.0 * 2.20462, places=2)

        resp = self.client.post("/stats/cache/clear")
        self.assertEqual(resp.json(), {"status": "cleared"})
        self.assertIsNone(
            self.api.stats_cache.fetch_weight_stats(d1, d2, "kg")
        )

    def test_current_body_weight_latest_log(self) -> None:
        d1 = "2023-01-01"
        d2 = "2023-01-02"
        self.client.post("/body_weight", params={"weight": 80.0, "date": d1})
        self.client.post("/body_weight", params={"weight": 85.0, "date": d2})

        weight = self.api.statistics._current_body_weight()
        self.assertAlmostEqual(weight, 85.0)

    def test_recommender_body_weight_latest_log(self) -> None:
        d1 = "2023-01-01"
        d2 = "2023-01-03"
        self.client.post("/body_weight", params={"weight": 70.0, "date": d1})
        self.client.post("/body_weight", params={"weight": 72.5, "date": d2})

        weight = self.api.recommender._current_body_weight()
        self.assertAlmostEqual(weight, 72.5)

    def test_body_weight_update_and_delete(self) -> None:
        d1 = "2023-01-01"
        resp = self.client.post("/body_weight", params={"weight": 80.0, "date": d1})
        self.assertEqual(resp.status_code, 200)
        eid = resp.json()["id"]

        d2 = "2023-01-02"
        resp = self.client.put(
            f"/body_weight/{eid}",
            params={"weight": 82.0, "date": d2},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "updated"})

        resp = self.client.get("/body_weight")
        self.assertEqual(len(resp.json()), 1)
        entry = resp.json()[0]
        self.assertEqual(entry["date"], d2)
        self.assertAlmostEqual(entry["weight"], 82.0)

        resp = self.client.delete(f"/body_weight/{eid}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "deleted"})

        resp = self.client.get("/body_weight")
        self.assertEqual(resp.json(), [])

    def test_body_weight_csv_export(self) -> None:
        d1 = "2023-01-01"
        d2 = "2023-01-02"
        self.client.post("/body_weight", params={"weight": 80.0, "date": d1})
        self.client.post("/body_weight", params={"weight": 82.0, "date": d2})
        resp = self.client.get("/body_weight/export_csv")
        self.assertEqual(resp.status_code, 200)
        lines = resp.text.strip().splitlines()
        self.assertEqual(lines[0], "Date,Weight")
        self.assertEqual(len(lines), 3)

    def test_bmi_endpoints(self) -> None:
        self.client.post("/body_weight", params={"weight": 80.0, "date": "2023-01-01"})
        self.client.post("/body_weight", params={"weight": 82.0, "date": "2023-01-02"})
        resp = self.client.post(
            "/settings/general",
            params={"height": 1.8},
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get("/stats/bmi")
        self.assertEqual(resp.status_code, 200)
        self.assertAlmostEqual(resp.json()["bmi"], round(82.0 / (1.8**2), 2))

        resp = self.client.get("/stats/bmi_history")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 2)
        self.assertAlmostEqual(data[0]["bmi"], round(80.0 / (1.8**2), 2))
        self.assertAlmostEqual(data[1]["bmi"], round(82.0 / (1.8**2), 2))

    def test_weight_forecast_endpoint(self) -> None:
        self.client.post("/body_weight", params={"weight": 80.0, "date": "2023-01-01"})
        self.client.post("/body_weight", params={"weight": 81.0, "date": "2023-01-02"})
        self.client.post("/body_weight", params={"weight": 82.0, "date": "2023-01-03"})
        resp = self.client.get("/stats/weight_forecast", params={"days": 2})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 2)
        slope = ExercisePrescription._weighted_linear_regression(
            [0, 1, 2], [80.0, 81.0, 82.0], [1, 2, 3]
        )
        self.assertAlmostEqual(data[0]["weight"], round(82.0 + slope * 1, 2))
        self.assertAlmostEqual(data[1]["weight"], round(82.0 + slope * 2, 2))

    def test_wellness_logging_and_stats(self) -> None:
        d1 = "2023-01-01"
        d2 = "2023-01-02"
        r1 = self.client.post(
            "/wellness",
            params={
                "date": d1,
                "calories": 2500.0,
                "sleep_hours": 8.0,
                "sleep_quality": 4.0,
                "stress_level": 2,
            },
        )
        self.assertEqual(r1.status_code, 200)
        id1 = r1.json()["id"]
        r2 = self.client.post(
            "/wellness",
            params={
                "date": d2,
                "calories": 2600.0,
                "sleep_hours": 7.5,
                "sleep_quality": 3.0,
                "stress_level": 3,
            },
        )
        self.assertEqual(r2.status_code, 200)
        id2 = r2.json()["id"]
        resp = self.client.get(
            "/wellness",
            params={"start_date": d1, "end_date": d2},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["id"], id1)
        self.assertAlmostEqual(data[0]["calories"], 2500.0)
        self.assertEqual(data[1]["id"], id2)
        summary = self.client.get(
            "/stats/wellness_summary",
            params={"start_date": d1, "end_date": d2},
        ).json()
        self.assertAlmostEqual(summary["avg_calories"], 2550.0)
        self.assertAlmostEqual(summary["avg_sleep"], 7.75)
        self.assertAlmostEqual(summary["avg_quality"], 3.5)
        self.assertAlmostEqual(summary["avg_stress"], 2.5)

    def test_wellness_update(self) -> None:
        d = "2023-01-01"
        resp = self.client.post(
            "/wellness",
            params={"date": d, "calories": 2000.0, "sleep_hours": 7.0},
        )
        self.assertEqual(resp.status_code, 200)
        wid = resp.json()["id"]

        upd = self.client.put(
            f"/wellness/{wid}",
            params={"date": d, "calories": 2100.0, "sleep_hours": 7.5},
        )
        self.assertEqual(upd.status_code, 200)

        entry = self.client.get("/wellness").json()[0]
        self.assertAlmostEqual(entry["calories"], 2100.0)

    def test_heart_rate_logging(self) -> None:
        self.client.post("/workouts", params={"date": "2023-01-01"})
        resp = self.client.post(
            "/workouts/1/heart_rate",
            params={"timestamp": "2023-01-01T10:00:00", "heart_rate": 120},
        )
        self.assertEqual(resp.status_code, 200)
        hr_id = resp.json()["id"]

        resp = self.client.get("/workouts/1/heart_rate")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], hr_id)
        self.assertEqual(data[0]["heart_rate"], 120)

        resp = self.client.get(
            "/heart_rate",
            params={"start_date": "2023-01-01", "end_date": "2023-01-02"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

        upd = self.client.put(
            f"/heart_rate/{hr_id}",
            params={"timestamp": "2023-01-01T10:05:00", "heart_rate": 125},
        )
        self.assertEqual(upd.status_code, 200)

        resp = self.client.get("/workouts/1/heart_rate")
        self.assertEqual(resp.json()[0]["heart_rate"], 125)

        del_resp = self.client.delete(f"/heart_rate/{hr_id}")
        self.assertEqual(del_resp.status_code, 200)
        self.assertEqual(self.client.get("/workouts/1/heart_rate").json(), [])

    def test_heart_rate_summary(self) -> None:
        self.client.post("/workouts", params={"date": "2023-01-01"})
        self.client.post(
            "/workouts/1/heart_rate",
            params={"timestamp": "2023-01-01T10:00:00", "heart_rate": 120},
        )
        self.client.post(
            "/workouts/1/heart_rate",
            params={"timestamp": "2023-01-01T10:05:00", "heart_rate": 130},
        )

        resp = self.client.get(
            "/stats/heart_rate_summary",
            params={"start_date": "2023-01-01", "end_date": "2023-01-02"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertAlmostEqual(data["avg"], 125.0)
        self.assertEqual(data["min"], 120.0)
        self.assertEqual(data["max"], 130.0)

    def test_heart_rate_zones(self) -> None:
        self.client.post("/workouts", params={"date": "2023-01-01"})
        self.client.post(
            "/workouts/1/heart_rate",
            params={"timestamp": "2023-01-01T10:00:00", "heart_rate": 120},
        )
        self.client.post(
            "/workouts/1/heart_rate",
            params={"timestamp": "2023-01-01T10:05:00", "heart_rate": 150},
        )

        resp = self.client.get(
            "/stats/heart_rate_zones",
            params={"start_date": "2023-01-01", "end_date": "2023-01-02"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 5)
        self.assertEqual(data[3]["count"], 1)
        self.assertEqual(data[3]["percent"], 50.0)
        self.assertEqual(data[4]["count"], 1)
        self.assertEqual(data[4]["percent"], 50.0)

    def test_step_logging(self) -> None:
        self.client.post("/workouts", params={"date": "2023-01-01"})
        resp = self.client.post(
            "/workouts/1/steps",
            params={"timestamp": "2023-01-01T10:00:00", "steps": 5000},
        )
        self.assertEqual(resp.status_code, 200)
        sid = resp.json()["id"]

        resp = self.client.get("/workouts/1/steps")
        self.assertEqual(len(resp.json()), 1)
        self.assertEqual(resp.json()[0]["id"], sid)

        resp = self.client.get(
            "/steps",
            params={"start_date": "2023-01-01", "end_date": "2023-01-02"},
        )
        self.assertEqual(len(resp.json()), 1)

        upd = self.client.put(
            f"/steps/{sid}",
            params={"timestamp": "2023-01-01T10:10:00", "steps": 5200},
        )
        self.assertEqual(upd.status_code, 200)

        resp = self.client.get("/workouts/1/steps")
        self.assertEqual(resp.json()[0]["steps"], 5200)

        del_resp = self.client.delete(f"/steps/{sid}")
        self.assertEqual(del_resp.status_code, 200)
        self.assertEqual(self.client.get("/workouts/1/steps").json(), [])

    def test_step_summary(self) -> None:
        self.client.post("/workouts", params={"date": "2023-01-01"})
        self.client.post(
            "/workouts/1/steps",
            params={"timestamp": "2023-01-01T10:00:00", "steps": 3000},
        )
        self.client.post(
            "/workouts/1/steps",
            params={"timestamp": "2023-01-01T12:00:00", "steps": 2000},
        )

        resp = self.client.get(
            "/stats/step_summary",
            params={"start_date": "2023-01-01", "end_date": "2023-01-02"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total"], 5000)
        self.assertEqual(data["avg"], 2500.0)

    def test_exercise_frequency(self) -> None:
        d1 = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
        d2 = datetime.date.today().isoformat()

        self.client.post("/workouts", params={"date": d1})
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )

        self.client.post("/workouts", params={"date": d2})
        self.client.post(
            "/workouts/2/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/2/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )

        resp = self.client.get(
            "/stats/exercise_frequency",
            params={"exercise": "Bench Press"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["exercise"], "Bench Press")
        self.assertAlmostEqual(data[0]["frequency_per_week"], 1.0)

    def test_exercise_notes(self) -> None:
        self.client.post("/workouts")
        resp = self.client.post(
            "/workouts/1/exercises",
            params={
                "name": "Bench Press",
                "equipment": "Olympic Barbell",
                "note": "Focus",
            },
        )
        self.assertEqual(resp.status_code, 200)
        ex_id = resp.json()["id"]

        resp = self.client.get("/workouts/1/exercises")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()[0]["note"], "Focus")

        resp = self.client.put(f"/exercises/{ex_id}/note", params={"note": "Updated"})
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get(f"/exercises/{ex_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["note"], "Updated")

    def test_favorite_exercises(self) -> None:
        resp = self.client.post(
            "/favorites/exercises",
            params={"name": "Bench Press"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "added"})

        resp = self.client.get("/favorites/exercises")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Bench Press", resp.json())

        resp = self.client.delete("/favorites/exercises/Bench Press")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "deleted"})

        resp = self.client.get("/favorites/exercises")
        self.assertNotIn("Bench Press", resp.json())

    def test_workout_tags(self) -> None:
        t_resp = self.client.post("/tags", params={"name": "Upper"})
        self.assertEqual(t_resp.status_code, 200)
        tid = t_resp.json()["id"]

        self.client.post("/workouts")
        add_resp = self.client.post("/workouts/1/tags", params={"tag_id": tid})
        self.assertEqual(add_resp.status_code, 200)

        list_resp = self.client.get("/workouts/1/tags")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(list_resp.json(), [{"id": tid, "name": "Upper"}])

        upd = self.client.put(f"/tags/{tid}", params={"name": "UpperA"})
        self.assertEqual(upd.status_code, 200)

        tags = self.client.get("/tags").json()
        self.assertEqual(tags[0]["name"], "UpperA")

        del_resp = self.client.delete(f"/workouts/1/tags/{tid}")
        self.assertEqual(del_resp.status_code, 200)
        self.assertEqual(self.client.get("/workouts/1/tags").json(), [])

        self.client.delete(f"/tags/{tid}")
        self.assertEqual(self.client.get("/tags").json(), [])

    def test_muscle_group_management(self) -> None:
        resp = self.client.post("/muscle_groups", params={"name": "Arms"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "added"})

        groups = self.client.get("/muscle_groups").json()
        self.assertIn("Arms", groups)

        assign = self.client.post(
            "/muscle_groups/Arms/muscles", params={"muscle": "Biceps Brachii"}
        )
        self.assertEqual(assign.status_code, 200)
        self.assertEqual(assign.json(), {"status": "assigned"})

        mus = self.client.get("/muscle_groups/Arms/muscles").json()
        self.assertEqual(mus, ["Biceps Brachii"])

        upd = self.client.put("/muscle_groups/Arms", params={"new_name": "Upper Arms"})
        self.assertEqual(upd.status_code, 200)

        groups = self.client.get("/muscle_groups").json()
        self.assertIn("Upper Arms", groups)

        delete = self.client.delete("/muscle_groups/Upper Arms")
        self.assertEqual(delete.status_code, 200)
        self.assertEqual(delete.json(), {"status": "deleted"})
        self.assertNotIn("Upper Arms", self.client.get("/muscle_groups").json())

    def test_template_workflow(self) -> None:
        resp = self.client.post(
            "/templates",
            params={"name": "Strength Base", "training_type": "strength"},
        )
        self.assertEqual(resp.status_code, 200)
        tid = resp.json()["id"]

        resp = self.client.post(
            f"/templates/{tid}/exercises",
            params={"name": "Squat", "equipment": "Olympic Barbell"},
        )
        self.assertEqual(resp.status_code, 200)
        ex_id = resp.json()["id"]

        resp = self.client.post(
            f"/template_exercises/{ex_id}/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        self.assertEqual(resp.status_code, 200)

        plan_date = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        resp = self.client.post(
            f"/templates/{tid}/plan",
            params={"date": plan_date},
        )
        self.assertEqual(resp.status_code, 200)
        plan_id = resp.json()["id"]

        resp = self.client.get(f"/planned_workouts/{plan_id}/exercises")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "Squat")

    def test_favorite_templates(self) -> None:
        resp = self.client.post(
            "/templates",
            params={"name": "Base", "training_type": "strength"},
        )
        self.assertEqual(resp.status_code, 200)
        tid = resp.json()["id"]

        add_resp = self.client.post(
            "/favorites/templates",
            params={"template_id": tid},
        )
        self.assertEqual(add_resp.status_code, 200)
        self.assertEqual(add_resp.json(), {"status": "added"})

        list_resp = self.client.get("/favorites/templates")
        self.assertEqual(list_resp.status_code, 200)
        self.assertIn(tid, list_resp.json())

        del_resp = self.client.delete(f"/favorites/templates/{tid}")
        self.assertEqual(del_resp.status_code, 200)
        self.assertEqual(del_resp.json(), {"status": "deleted"})

        list_resp = self.client.get("/favorites/templates")
        self.assertNotIn(tid, list_resp.json())

    def test_favorite_workouts(self) -> None:
        self.client.post("/workouts")
        add_resp = self.client.post(
            "/favorites/workouts",
            params={"workout_id": 1},
        )
        self.assertEqual(add_resp.status_code, 200)
        self.assertEqual(add_resp.json(), {"status": "added"})

        list_resp = self.client.get("/favorites/workouts")
        self.assertEqual(list_resp.status_code, 200)
        self.assertIn(1, list_resp.json())

        del_resp = self.client.delete("/favorites/workouts/1")
        self.assertEqual(del_resp.status_code, 200)
        self.assertEqual(del_resp.json(), {"status": "deleted"})

        list_resp = self.client.get("/favorites/workouts")
        self.assertNotIn(1, list_resp.json())

    def test_default_equipment(self) -> None:
        resp = self.client.post(
            "/default_equipment",
            params={"exercise_name": "Bench Press", "equipment_name": "Olympic Barbell"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "set"})

        resp = self.client.get("/default_equipment/Bench Press")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"equipment_name": "Olympic Barbell"})

        lst = self.client.get("/default_equipment").json()
        self.assertIn({"exercise_name": "Bench Press", "equipment_name": "Olympic Barbell"}, lst)

        resp = self.client.delete("/default_equipment/Bench Press")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "deleted"})

        resp = self.client.get("/default_equipment/Bench Press")
        self.assertIsNone(resp.json()["equipment_name"])

    def test_copy_workout_to_template(self) -> None:
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        resp = self.client.post("/workouts/1/copy_to_template")
        self.assertEqual(resp.status_code, 200)
        tid = resp.json()["id"]
        detail = self.client.get(f"/templates/{tid}/exercises")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(len(detail.json()), 1)

    def test_duplicate_workout(self) -> None:
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        new_date = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        resp = self.client.post(
            "/workouts/1/duplicate",
            params={"date": new_date},
        )
        self.assertEqual(resp.status_code, 200)
        dup_id = resp.json()["id"]
        detail = self.client.get(f"/workouts/{dup_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["date"], new_date)
        sets = self.client.get(f"/workouts/{dup_id}/exercises")
        self.assertEqual(len(sets.json()), 1)

    def test_template_reordering(self) -> None:
        tids = []
        for name in ["T1", "T2", "T3"]:
            resp = self.client.post(
                "/templates",
                params={"name": name, "training_type": "strength"},
            )
            self.assertEqual(resp.status_code, 200)
            tids.append(resp.json()["id"])

        order = ",".join(map(str, [tids[1], tids[2], tids[0]]))
        resp = self.client.post("/templates/order", params={"order": order})
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get("/templates")
        ids = [t["id"] for t in resp.json()]
        self.assertEqual(ids, [tids[1], tids[2], tids[0]])

    def test_template_share(self) -> None:
        resp = self.client.post(
            "/templates", params={"name": "Share", "training_type": "strength"}
        )
        tid = resp.json()["id"]
        self.client.post(
            f"/templates/{tid}/exercises",
            params={"name": "Bench", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/template_exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        resp = self.client.get(f"/templates/{tid}/share")
        self.assertEqual(resp.status_code, 200)
        text = resp.json()["text"]
        self.assertIn("Bench", text)

    def test_rating_history_and_stats(self) -> None:
        d1 = "2023-01-01"
        d2 = "2023-01-02"
        self.client.post(
            "/workouts",
            params={"date": d1, "training_type": "strength", "rating": 4},
        )
        self.client.post(
            "/workouts",
            params={"date": d2, "training_type": "strength", "rating": 5},
        )

        hist_resp = self.client.get(
            "/stats/rating_history",
            params={"start_date": d1, "end_date": d2},
        )
        self.assertEqual(hist_resp.status_code, 200)
        self.assertEqual(
            hist_resp.json(),
            [
                {"date": d1, "rating": 4},
                {"date": d2, "rating": 5},
            ],
        )

        stats_resp = self.client.get(
            "/stats/rating_stats",
            params={"start_date": d1, "end_date": d2},
        )
        self.assertEqual(stats_resp.status_code, 200)
        stats = stats_resp.json()
        self.assertAlmostEqual(stats["avg"], 4.5)
        self.assertEqual(stats["min"], 4)
        self.assertEqual(stats["max"], 5)

    def test_rating_distribution(self) -> None:
        d1 = "2023-01-01"
        d2 = "2023-01-02"
        self.client.post("/workouts", params={"date": d1, "rating": 4})
        self.client.post("/workouts", params={"date": d2, "rating": 5})
        resp = self.client.get(
            "/stats/rating_distribution",
            params={"start_date": d1, "end_date": d2},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.json(),
            [{"rating": 4, "count": 1}, {"rating": 5, "count": 1}],
        )

    def test_calendar_endpoint(self) -> None:
        today = datetime.date.today().isoformat()
        tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        self.client.post("/workouts", params={"date": today})
        self.client.post(
            "/planned_workouts",
            params={"date": tomorrow, "training_type": "strength"},
        )
        resp = self.client.get(
            "/calendar",
            params={"start_date": today, "end_date": tomorrow},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["date"], today)
        self.assertFalse(data[0]["planned"])
        self.assertEqual(data[1]["date"], tomorrow)
        self.assertTrue(data[1]["planned"])

    def test_goal_endpoints(self) -> None:
        start = datetime.date.today().isoformat()
        target = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()

        resp = self.client.post(
            "/goals",
            params={
                "exercise_name": "Squat",
                "name": "Squat PR",
                "target_value": 200.0,
                "unit": "kg",
                "start_date": start,
                "target_date": target,
            },
        )
        self.assertEqual(resp.status_code, 200)
        gid = resp.json()["id"]

        resp = self.client.get("/goals")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "Squat PR")
        self.assertEqual(data[0]["exercise_name"], "Squat")

        resp = self.client.put(
            f"/goals/{gid}",
            params={"achieved": True},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "updated"})

        resp = self.client.get("/goals")
        self.assertTrue(resp.json()[0]["achieved"])

        resp = self.client.delete(f"/goals/{gid}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "deleted"})

        self.assertEqual(self.client.get("/goals").json(), [])

    def test_goal_integration_with_recommendation(self) -> None:
        start = datetime.date.today()
        target = start + datetime.timedelta(days=30)

        resp = self.client.post("/workouts")
        self.assertEqual(resp.status_code, 200)
        wid_hist = resp.json()["id"]

        resp = self.client.post(
            f"/workouts/{wid_hist}/exercises",
            params={"name": "Squat", "equipment": "Olympic Barbell"},
        )
        self.assertEqual(resp.status_code, 200)
        ex_hist = resp.json()["id"]

        self.client.post(
            f"/exercises/{ex_hist}/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        self.client.post(
            f"/exercises/{ex_hist}/sets",
            params={"reps": 5, "weight": 105.0, "rpe": 8},
        )
        self.client.post(
            f"/exercises/{ex_hist}/sets",
            params={"reps": 5, "weight": 110.0, "rpe": 8},
        )

        resp = self.client.post("/workouts")
        self.assertEqual(resp.status_code, 200)
        wid = resp.json()["id"]

        resp = self.client.post(
            f"/workouts/{wid}/exercises",
            params={"name": "Squat", "equipment": "Olympic Barbell"},
        )
        self.assertEqual(resp.status_code, 200)
        ex_id = resp.json()["id"]

        goal_resp = self.client.post(
            "/goals",
            params={
                "exercise_name": "Squat",
                "name": "Squat Goal",
                "target_value": 150.0,
                "unit": "kg",
                "start_date": start.isoformat(),
                "target_date": target.isoformat(),
            },
        )
        self.assertEqual(goal_resp.status_code, 200)

        active = self.api.goals.fetch_active_by_exercise(
            "Squat", today=start.isoformat()
        )
        self.assertEqual(len(active), 1)
        self.assertAlmostEqual(active[0]["target_value"], 150.0)

        rec = self.client.post(f"/exercises/{ex_id}/recommend_next")
        self.assertEqual(rec.status_code, 200)
        data = rec.json()
        self.assertIn("weight", data)
        self.assertIn("reps", data)

    def test_workout_consistency_endpoint(self) -> None:
        d0 = datetime.date.today() - datetime.timedelta(days=14)
        d1 = datetime.date.today() - datetime.timedelta(days=7)
        d2 = datetime.date.today()
        for d in [d0, d1, d2]:
            self.client.post("/workouts", params={"date": d.isoformat()})

        resp = self.client.get("/stats/workout_consistency")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertAlmostEqual(data["consistency"], 0.0)
        self.assertAlmostEqual(data["average_gap"], 7.0)

    def test_ai_plan_endpoint(self) -> None:
        weights = [100.0, 105.0, 110.0, 112.5, 115.0]
        for w in weights:
            res = self.client.post("/workouts")
            wid = res.json()["id"]
            ex_res = self.client.post(
                f"/workouts/{wid}/exercises",
                params={"name": "Bench", "equipment": "Olympic Barbell"},
            )
            ex_id = ex_res.json()["id"]
            self.client.post(
                f"/exercises/{ex_id}/sets",
                params={"reps": 5, "weight": w, "rpe": 8},
            )
        self.client.post(
            "/wellness",
            params={
                "date": datetime.date.today().isoformat(),
                "calories": 2500.0,
                "sleep_hours": 8.0,
                "sleep_quality": 5.0,
                "stress_level": 3,
            },
        )
        plan_date = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        resp = self.client.post(
            "/planned_workouts/auto_plan",
            params={"date": plan_date, "exercises": "Bench@Olympic Barbell"},
        )
        self.assertEqual(resp.status_code, 200)
        pid = resp.json()["id"]
        ex_resp = self.client.get(f"/planned_workouts/{pid}/exercises")
        self.assertEqual(len(ex_resp.json()), 1)
        planned_ex_id = ex_resp.json()[0]["id"]
        sets_resp = self.client.get(f"/planned_exercises/{planned_ex_id}/sets")
        self.assertEqual(sets_resp.status_code, 200)
        sets_data = sets_resp.json()
        self.assertEqual(len(sets_data), 1)
        presc = ExercisePrescription.exercise_prescription(
            weights,
            [5] * len(weights),
            list(range(len(weights))),
            [8] * len(weights),
            calories=[2500.0],
            sleep_hours=[8.0],
            sleep_quality=[5.0],
            stress_levels=[3],
            body_weight=80.0,
            months_active=1.0,
            workouts_per_month=len(weights),
        )
        expected = presc["prescription"][0]
        self.assertAlmostEqual(sets_data[0]["weight"], expected["weight"], places=1)
        self.assertEqual(sets_data[0]["reps"], expected["reps"])

    def test_git_pull_endpoint(self) -> None:
        remote_dir = os.path.join(os.getcwd(), "git_remote")
        repo_dir = os.path.expanduser("~/thebuilder")
        for path in [remote_dir, repo_dir]:
            if os.path.exists(path):
                shutil.rmtree(path)
        subprocess.run(["git", "init", "--bare", remote_dir], check=True)
        subprocess.run(["git", "clone", remote_dir, repo_dir], check=True)
        temp_clone = os.path.join(os.getcwd(), "temp_clone")
        subprocess.run(["git", "clone", remote_dir, temp_clone], check=True)
        with open(os.path.join(temp_clone, "file.txt"), "w", encoding="utf-8") as f:
            f.write("data")
        subprocess.run(["git", "add", "file.txt"], cwd=temp_clone, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=temp_clone, check=True)
        subprocess.run(["git", "push"], cwd=temp_clone, check=True)
        shutil.rmtree(temp_clone)

        resp = self.client.post("/settings/git_pull")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "pulled")
        self.assertTrue(os.path.exists(os.path.join(repo_dir, "file.txt")))
        shutil.rmtree(remote_dir)
        shutil.rmtree(repo_dir)

    def test_ai_plan_requires_only_history(self) -> None:
        """AI planner should work with only workout history available."""
        weights = [60.0, 62.5, 65.0]
        for w in weights:
            w_res = self.client.post("/workouts")
            wid = w_res.json()["id"]
            ex_res = self.client.post(
                f"/workouts/{wid}/exercises",
                params={"name": "Squat", "equipment": "Power Rack"},
            )
            ex_id = ex_res.json()["id"]
            self.client.post(
                f"/exercises/{ex_id}/sets",
                params={"reps": 5, "weight": w, "rpe": 8},
            )

        plan_date = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        resp = self.client.post(
            "/planned_workouts/auto_plan",
            params={"date": plan_date, "exercises": "Squat@Power Rack"},
        )
        self.assertEqual(resp.status_code, 200)
        pid = resp.json()["id"]
        ex_resp = self.client.get(f"/planned_workouts/{pid}/exercises")
        self.assertEqual(len(ex_resp.json()), 1)
        planned_ex_id = ex_resp.json()[0]["id"]
        sets_resp = self.client.get(f"/planned_exercises/{planned_ex_id}/sets")
        self.assertEqual(sets_resp.status_code, 200)
        sets_data = sets_resp.json()
        self.assertGreaterEqual(len(sets_data), 1)

    def test_goal_plan_endpoint(self) -> None:
        """Goal planner should create plan from active goals."""
        # create history
        wid = self.client.post("/workouts").json()["id"]
        ex_id = self.client.post(
            f"/workouts/{wid}/exercises",
            params={"name": "Bench", "equipment": "Olympic Barbell"},
        ).json()["id"]
        self.client.post(
            f"/exercises/{ex_id}/sets",
            params={"reps": 5, "weight": 60.0, "rpe": 8},
        )
        today = datetime.date.today().isoformat()
        target = (datetime.date.today() + datetime.timedelta(days=7)).isoformat()
        g_resp = self.client.post(
            "/goals",
            params={
                "exercise_name": "Bench",
                "name": "1RM",
                "target_value": 80.0,
                "unit": "kg",
                "start_date": today,
                "target_date": target,
            },
        )
        self.assertEqual(g_resp.status_code, 200)
        plan_date = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        resp = self.client.post(
            "/planned_workouts/goal_plan",
            params={"date": plan_date},
        )
        self.assertEqual(resp.status_code, 200)
        pid = resp.json()["id"]
        ex_resp = self.client.get(f"/planned_workouts/{pid}/exercises")
        self.assertEqual(len(ex_resp.json()), 1)

    def test_autoplanner_status_success_and_error(self) -> None:
        """Autoplanner status should report last run and errors."""
        # Trigger error first
        plan_date = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        resp_err = self.client.post(
            "/planned_workouts/auto_plan",
            params={"date": plan_date, "exercises": "Unknown"},
        )
        self.assertEqual(resp_err.status_code, 400)
        # Now add history for success
        wid = self.client.post("/workouts").json()["id"]
        ex_id = self.client.post(
            f"/workouts/{wid}/exercises",
            params={"name": "Bench", "equipment": "Olympic Barbell"},
        ).json()["id"]
        self.client.post(
            f"/exercises/{ex_id}/sets",
            params={"reps": 5, "weight": 60.0, "rpe": 8},
        )
        resp_ok = self.client.post(
            "/planned_workouts/auto_plan",
            params={"date": plan_date, "exercises": "Bench@Olympic Barbell"},
        )
        self.assertEqual(resp_ok.status_code, 200)

        status = self.client.get("/autoplanner/status").json()
        self.assertIsNotNone(status["last_success"])
        self.assertGreaterEqual(len(status["errors"]), 1)
        self.assertIsNotNone(status["prescription_last_success"])
        self.assertGreaterEqual(len(status["prescription_errors"]), 1)
        self.assertTrue(any(m["name"] == "performance_model" for m in status["models"]))

    def test_autoplanner_model_toggle(self) -> None:
        """Disabling and enabling a model should affect status output."""
        # volume model should be present by default
        status = self.client.get("/autoplanner/status").json()
        self.assertTrue(any(m["name"] == "volume_model" for m in status["models"]))

    def test_bulk_heart_rate_upload(self) -> None:
        self.client.post("/workouts")
        data = [
            {"timestamp": "2023-01-01T10:00:00", "heart_rate": 120},
            {"timestamp": "2023-01-01T10:01:00", "heart_rate": 125},
        ]
        resp = self.client.post("/workouts/1/heart_rate/bulk", json=data)
        self.assertEqual(resp.status_code, 200)
        ids = resp.json()["ids"]
        self.assertEqual(len(ids), 2)
        rows = self.client.get("/workouts/1/heart_rate").json()
        self.assertEqual(len(rows), 2)

    def test_stale_goals_endpoint(self) -> None:
        today = datetime.date.today().isoformat()
        past = (datetime.date.today() - datetime.timedelta(days=10)).isoformat()
        self.client.post(
            "/goals",
            params={
                "exercise_name": "Bench Press",
                "name": "old",
                "target_value": 100.0,
                "unit": "kg",
                "start_date": past,
                "target_date": past,
            },
        )
        resp = self.client.get("/goals/stale")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

    def test_autoplan_config(self) -> None:
        resp = self.client.post(
            "/autoplanner/config", params={"days_ahead": 5, "intensity": "high"}
        )
        self.assertEqual(resp.status_code, 200)
        cfg = self.client.get("/autoplanner/config").json()
        self.assertEqual(cfg["days_ahead"], 5)
        self.assertEqual(cfg["intensity"], "high")

    def test_workout_completion_webhook(self) -> None:
        from http.server import BaseHTTPRequestHandler, HTTPServer
        import threading

        received: list = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("content-length", 0))
                body = self.rfile.read(length)
                received.append(json.loads(body))
                self.send_response(200)
                self.end_headers()

        server = HTTPServer(("localhost", 0), Handler)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        url = f"http://localhost:{server.server_address[1]}"
        self.client.post("/settings/general", params={"webhook_url": url})
        wid = self.client.post("/workouts").json()["id"]
        self.client.post(f"/workouts/{wid}/finish")
        server.shutdown()
        thread.join()
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["workout_id"], wid)

    def test_workout_search_endpoint(self) -> None:
        today = datetime.date.today().isoformat()
        self.client.post("/workouts", params={"notes": "Home session"})
        self.client.post("/workouts", params={"notes": "Gym session"})
        resp = self.client.get("/workouts/search", params={"query": "Gym"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [{"id": 2, "date": today}])

    def test_exercise_search_endpoint(self) -> None:
        resp = self.client.get("/exercises/search", params={"query": "Bench"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Barbell Bench Press", resp.json())

    def test_workout_streak_endpoint(self) -> None:
        today = datetime.date.today()
        for i in range(3):
            date = (today - datetime.timedelta(days=2 - i)).isoformat()
            self.client.post("/workouts", params={"date": date})
        resp = self.client.get("/gamification/streak")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"current": 3, "record": 3})

        # disable both training and prediction
        resp = self.client.post(
            "/settings/general",
            params={
                "ml_volume_training_enabled": False,
                "ml_volume_prediction_enabled": False,
            },
        )
        self.assertEqual(resp.status_code, 200)
        status = self.client.get("/autoplanner/status").json()
        self.assertFalse(any(m["name"] == "volume_model" for m in status["models"]))

        # enable again
        resp = self.client.post(
            "/settings/general",
            params={
                "ml_volume_training_enabled": True,
                "ml_volume_prediction_enabled": True,
            },
        )
        self.assertEqual(resp.status_code, 200)
        status = self.client.get("/autoplanner/status").json()
        self.assertTrue(any(m["name"] == "volume_model" for m in status["models"]))

    def test_recent_equipment_and_muscles(self) -> None:
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        resp = self.client.get("/equipment/recent")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Olympic Barbell", resp.json())
        resp = self.client.get("/muscles/recent")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Pectoralis Major", resp.json())

    def test_health_endpoint(self) -> None:
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "ok")

    def test_email_weekly_report(self) -> None:
        # create data within last week
        today = datetime.date.today().isoformat()
        self.client.post("/workouts", params={"date": today})
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        self.client.post(
            "/settings/general",
            params={
                "email_weekly_enabled": True,
                "weekly_report_email": "user@example.com",
            },
        )

        resp = self.client.post("/reports/email_weekly")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "sent")

        logs = self.client.get("/reports/email_logs").json()
        self.assertEqual(len(logs), 1)
        log = logs[0]
        self.assertEqual(log["address"], "user@example.com")
        summary = json.loads(log["summary"])
        self.assertIn("workouts", summary)

    def test_backup_and_restore(self) -> None:
        self.client.post("/workouts")
        resp = self.client.get("/settings/backup")
        self.assertEqual(resp.status_code, 200)
        data = resp.content
        os.remove(self.db_path)
        resp = self.client.post(
            "/settings/restore",
            content=data,
            headers={"Content-Type": "application/octet-stream"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "restored"})
        resp = self.client.get("/workouts")
        self.assertEqual(len(resp.json()), 1)

    def test_notifications_crud(self) -> None:
        resp = self.client.post("/notifications", json="Test note")
        self.assertEqual(resp.status_code, 200)
        nid = resp.json()["id"]

        resp = self.client.get("/notifications")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)
        self.assertFalse(resp.json()[0]["read"])

        resp = self.client.put(f"/notifications/{nid}/read")
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get("/notifications", params={"unread_only": True})
        self.assertEqual(resp.json(), [])

        resp = self.client.get("/notifications/unread_count")
        self.assertEqual(resp.json()["count"], 0)

    def test_challenges_crud(self) -> None:
        resp = self.client.post("/challenges", params={"name": "30-day", "target": 30})
        self.assertEqual(resp.status_code, 200)
        cid = resp.json()["id"]

        resp = self.client.get("/challenges")
        self.assertEqual(len(resp.json()), 1)
        self.assertEqual(resp.json()[0]["progress"], 0)

        resp = self.client.put(f"/challenges/{cid}/progress", params={"progress": 10})
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get("/challenges")
        self.assertEqual(resp.json()[0]["progress"], 10)

        resp = self.client.post(
            f"/challenges/{cid}/complete", params={"completed": True}
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get("/challenges")
        self.assertTrue(resp.json()[0]["completed"])

    def test_fuzzy_equipment_search(self) -> None:
        resp = self.client.get("/equipment/search", params={"query": "olympic barbel"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Olympic Barbell", resp.json())

    def test_fuzzy_muscle_search(self) -> None:
        resp = self.client.get("/muscles/search", params={"query": "pectorls"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Pectoralis Major", resp.json())

    def test_plan_progress(self) -> None:
        resp = self.client.post(
            "/planned_workouts",
            params={"date": "2024-01-01", "training_type": "strength"},
        )
        pid = resp.json()["id"]
        self.client.post(
            f"/planned_workouts/{pid}/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            f"/planned_exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        resp = self.client.get(f"/planned_workouts/{pid}/progress")
        self.assertEqual(resp.json()["percent"], 0.0)
        self.client.post(f"/planned_workouts/{pid}/use")
        resp = self.client.get(f"/planned_workouts/{pid}/progress")
        self.assertEqual(resp.json()["percent"], 100.0)

    def test_workout_reactions(self) -> None:
        wid = self.client.post("/workouts").json()["id"]
        resp = self.client.post(f"/workouts/{wid}/reactions", json="👍")
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get(f"/workouts/{wid}/reactions")
        self.assertIn({"emoji": "👍", "count": 1}, resp.json())

    def test_workout_calories(self) -> None:
        wid = self.client.post("/workouts").json()["id"]
        self.client.post(
            f"/workouts/{wid}/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 10, "weight": 100.0, "rpe": 8},
        )
        self.client.post(f"/workouts/{wid}/start")
        self.client.post(f"/workouts/{wid}/finish")
        resp = self.client.get(f"/workouts/{wid}/calories")
        self.assertGreater(resp.json()["calories"], 0)

    def test_workout_share(self) -> None:
        wid = self.client.post("/workouts").json()["id"]
        self.client.post(
            f"/workouts/{wid}/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        resp = self.client.get(f"/workouts/{wid}/share")
        self.assertIn("Bench Press", resp.json()["text"])

    def test_bookmarks_setting(self) -> None:
        resp = self.client.post("/settings/bookmarks", json="overview,progress")
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get("/settings/bookmarks")
        self.assertEqual(resp.json()["views"], ["overview", "progress"])

    def test_create_workout_future_date_error(self) -> None:
        future = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        resp = self.client.post("/workouts", params={"date": future})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["detail"], "date cannot be in the future")

    def test_exercise_catalog_not_found(self) -> None:
        resp = self.client.get("/exercise_catalog/Unknown")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["detail"], "not found")

    def test_update_tag_not_found(self) -> None:
        resp = self.client.put("/tags/99", params={"name": "x"})
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["detail"], "tag not found")

    def test_goal_progress_endpoint(self) -> None:
        today = datetime.date.today().isoformat()
        target = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
        self.client.post("/workouts", params={"date": today})
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        self.client.post(
            "/goals",
            params={
                "exercise_name": "Bench Press",
                "name": "Bench",
                "target_value": 120.0,
                "unit": "kg",
                "start_date": today,
                "target_date": target,
            },
        )
        resp = self.client.get("/goals/1/progress")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertIn("progress", data[0])

    def test_reorder_planned_workouts(self) -> None:
        d1 = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        d2 = (datetime.date.today() + datetime.timedelta(days=2)).isoformat()
        id1 = self.client.post("/planned_workouts", params={"date": d1}).json()["id"]
        id2 = self.client.post("/planned_workouts", params={"date": d2}).json()["id"]
        resp = self.client.post("/planned_workouts/order", params={"order": f"{id2},{id1}"})
        self.assertEqual(resp.status_code, 200)
        data = self.client.get("/planned_workouts", params={"sort_by": "position", "descending": False}).json()
        self.assertEqual([d["id"] for d in data], [id2, id1])

    def test_workout_history_time_filter(self) -> None:
        self.client.post("/workouts", params={"date": "2024-01-01", "start_time": "08:00", "end_time": "09:00"})
        self.client.post("/workouts", params={"date": "2024-01-02", "start_time": "18:00", "end_time": "19:00"})
        resp = self.client.get(
            "/workouts/history",
            params={"start_date": "2024-01-01", "end_date": "2024-01-02", "start_time": "17:00"},
        )
        self.assertEqual(len(resp.json()), 1)

    def test_exercise_catalog_sort(self) -> None:
        self.client.post(
            "/exercise_catalog",
            params={
                "muscle_group": "Chest",
                "name": "ZZ Press",
                "variants": "",
                "equipment_names": "Dumbbell",
                "primary_muscle": "Chest",
            },
        )
        self.client.post(
            "/exercise_catalog",
            params={
                "muscle_group": "Arms",
                "name": "AA Curl",
                "variants": "",
                "equipment_names": "Dumbbell",
                "primary_muscle": "Biceps",
            },
        )
        resp = self.client.get("/exercise_catalog", params={"sort_by": "muscle_group"})
        self.assertEqual(resp.json()[0], "AA Curl")

    def test_hashtag_tags(self) -> None:
        resp = self.client.post("/workouts", params={"notes": "great #fun"})
        wid = resp.json()["id"]
        tags = self.client.get(f"/workouts/{wid}/tags").json()
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0]["name"], "fun")

    def test_report_pdf_endpoint(self) -> None:
        os.makedirs("reports", exist_ok=True)
        path = "reports/test.pdf"
        with open(path, "wb") as f:
            f.write(b"%PDF-1.4\n%%EOF")
        resp = self.client.get("/reports/test.pdf")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"], "application/pdf")

    def test_progression_pdf_endpoint(self) -> None:
        # minimal workout and set to create progression data
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        resp = self.client.get(
            "/stats/progression_pdf",
            params={"exercise": "Bench Press"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"], "application/pdf")



class RateLimitTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.api = GymAPI(
            db_path="rate.db",
            yaml_path="rate.yaml",
            start_scheduler=False,
            rate_limit=2,
            rate_window=60,
        )
        self.client = TestClient(self.api.app)

    def tearDown(self) -> None:
        if os.path.exists("rate.db"):
            os.remove("rate.db")
        if os.path.exists("rate.yaml"):
            os.remove("rate.yaml")

    def test_rate_limit(self) -> None:
        self.client.get("/health")
        self.client.get("/health")
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 429)

class PWAEndpointsTest(unittest.TestCase):
    def setUp(self) -> None:
        api = GymAPI(start_scheduler=False)
        self.client = TestClient(api.app)

    def test_manifest_and_sw(self) -> None:
        resp = self.client.get("/manifest.json")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("name", resp.json())
        resp = self.client.get("/sw.js")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("addEventListener", resp.text)
        self.assertIn("offline_search", resp.text)


class RestNoteTestCase(unittest.TestCase):
    def setUp(self) -> None:
        api = GymAPI(start_scheduler=False)
        self.client = TestClient(api.app)

    def test_rest_note_update(self) -> None:
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Squat", "equipment": "Rack"},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        resp = self.client.put("/sets/1/rest_note", params={"note": "tough"})
        self.assertEqual(resp.status_code, 200)
        detail = self.client.get("/sets/1").json()
        self.assertEqual(detail["rest_note"], "tough")


class CompareProgressTestCase(unittest.TestCase):
    def setUp(self) -> None:
        api = GymAPI(start_scheduler=False)
        self.client = TestClient(api.app)

    def test_compare_progress(self) -> None:
        d = "2024-01-01"
        self.client.post("/workouts", params={"date": d})
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        self.client.post("/workouts", params={"date": d})
        self.client.post(
            "/workouts/2/exercises",
            params={"name": "Overhead Press", "equipment": "Olympic Barbell"},
        )
        self.client.post(
            "/exercises/2/sets",
            params={"reps": 5, "weight": 90.0, "rpe": 8},
        )
        resp = self.client.get(
            "/stats/compare_progress",
            params={"exercise1": "Bench Press", "exercise2": "Overhead Press"},
        )
        self.assertEqual(resp.status_code, 200)


class SummaryImageTestCase(unittest.TestCase):
    def setUp(self) -> None:
        api = GymAPI(start_scheduler=False)
        self.client = TestClient(api.app)

    def test_summary_image_endpoint(self) -> None:
        self.client.post("/workouts")
        self.client.post(
            "/workouts/1/exercises",
            params={"name": "Bench", "equipment": "Bar"},
        )
        self.client.post(
            "/exercises/1/sets",
            params={"reps": 5, "weight": 100.0, "rpe": 8},
        )
        resp = self.client.get("/workouts/1/summary_image")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"], "image/png")
        self.assertGreater(len(resp.content), 0)

