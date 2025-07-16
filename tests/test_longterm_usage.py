import os
import datetime
import sqlite3
import unittest
from fastapi.testclient import TestClient

import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from rest_api import GymAPI
from tools import MathTools


class LongTermUsageTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = "test_longterm.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.api = GymAPI(db_path=self.db_path)
        self.client = TestClient(self.api.app)

    def tearDown(self) -> None:
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_partial_long_term_usage(self) -> None:
        start = datetime.date.today() - datetime.timedelta(days=27)
        end = start + datetime.timedelta(days=27)

        # add custom equipment
        resp = self.client.post(
            "/equipment",
            params={
                "equipment_type": "Free Weights",
                "name": "Adj Dumbbell",
                "muscles": "Biceps Brachii",
            },
        )
        self.assertEqual(resp.status_code, 200)

        # add custom exercise
        resp = self.client.post(
            "/exercise_catalog",
            params={
                "muscle_group": "Arms",
                "name": "Incline Bicep Curl",
                "variants": "",
                "equipment_names": "Adj Dumbbell",
                "primary_muscle": "Biceps Brachii",
            },
        )
        self.assertEqual(resp.status_code, 200)

        # add second equipment and exercise
        resp = self.client.post(
            "/equipment",
            params={
                "equipment_type": "Free Weights",
                "name": "Hex Bar",
                "muscles": "Quadriceps",
            },
        )
        self.assertEqual(resp.status_code, 200)
        resp = self.client.post(
            "/exercise_catalog",
            params={
                "muscle_group": "Legs",
                "name": "Trap Bar Deadlift",
                "variants": "",
                "equipment_names": "Hex Bar",
                "primary_muscle": "Quadriceps",
            },
        )
        self.assertEqual(resp.status_code, 200)

        expected_volumes: dict[str, float] = {}
        bench_volume_total = 0.0
        bench_sets = 0
        bench_rpe_total = 0
        max_1rm = 0.0
        success_count = 0

        for i in range(14):
            w_date = start + datetime.timedelta(days=i * 2)
            date_str = w_date.isoformat()
            if i % 5 == 2:
                # planned workout flow with three sets
                resp = self.client.post(
                    "/planned_workouts",
                    params={"date": date_str, "training_type": "strength"},
                )
                self.assertEqual(resp.status_code, 200)
                plan_id = resp.json()["id"]
                resp = self.client.post(
                    f"/planned_workouts/{plan_id}/exercises",
                    params={"name": "Bench Press", "equipment": "Olympic Barbell"},
                )
                self.assertEqual(resp.status_code, 200)
                plan_ex = resp.json()["id"]
                for _ in range(3):
                    resp = self.client.post(
                        f"/planned_exercises/{plan_ex}/sets",
                        params={"reps": 5, "weight": 100 + 2 * i, "rpe": 8},
                    )
                    self.assertEqual(resp.status_code, 200)
                resp = self.client.post(f"/planned_workouts/{plan_id}/use")
                self.assertEqual(resp.status_code, 200)
                workout_id = resp.json()["id"]
                resp = self.client.get(f"/workouts/{workout_id}/exercises")
                bench_id = resp.json()[0]["id"]
                reps = 5
                weight = 100.0 + 2 * i
                volume_bench = 3 * reps * weight
                est = MathTools.epley_1rm(weight, reps)
                if est > max_1rm:
                    max_1rm = est
                ids = []
            else:
                resp = self.client.post(
                    "/workouts", params={"date": date_str}
                )
                self.assertEqual(resp.status_code, 200)
                workout_id = resp.json()["id"]

                resp = self.client.post(
                    f"/workouts/{workout_id}/exercises",
                    params={"name": "Bench Press", "equipment": "Olympic Barbell"},
                )
                self.assertEqual(resp.status_code, 200)
                bench_id = resp.json()["id"]

                reps = 5
                weight = 100.0 + 2 * i
                ids = []
                for _ in range(3):
                    r = self.client.post(
                        f"/exercises/{bench_id}/sets",
                        params={"reps": reps, "weight": weight, "rpe": 8},
                    )
                    self.assertEqual(r.status_code, 200)
                    ids.append(r.json()["id"])
                    est = MathTools.epley_1rm(weight, reps)
                    if est > max_1rm:
                        max_1rm = est
                volume_bench = 3 * reps * weight

            if i % 9 == 1:
                r = self.client.put(
                    f"/sets/{ids[0]}",
                    params={"reps": 6, "weight": 105.0, "rpe": 9},
                )
                self.assertEqual(r.status_code, 200)
                volume_bench += 6 * 105.0 - 5 * weight
                bench_rpe_total += 1
                est = MathTools.epley_1rm(105.0, 6)
                if est > max_1rm:
                    max_1rm = est

            resp = self.client.post(
                f"/exercises/{bench_id}/recommend_next"
            )
            if resp.status_code == 200:
                success_count += 1

            resp = self.client.post(
                f"/workouts/{workout_id}/exercises",
                params={"name": "Incline Bicep Curl", "equipment": "Adj Dumbbell"},
            )
            self.assertEqual(resp.status_code, 200)
            curl_id = resp.json()["id"]
            curl_weight = 40.0 + i
            for _ in range(3):
                r = self.client.post(
                    f"/exercises/{curl_id}/sets",
                    params={"reps": 8, "weight": curl_weight, "rpe": 7},
                )
                self.assertEqual(r.status_code, 200)
            volume_curl = 3 * 8 * curl_weight

            volume_deadlift = 0.0
            if i >= 6:
                resp = self.client.post(
                    f"/workouts/{workout_id}/exercises",
                    params={"name": "Trap Bar Deadlift", "equipment": "Hex Bar"},
                )
                self.assertEqual(resp.status_code, 200)
                dead_id = resp.json()["id"]
                weight_dl = 150.0 + i
                for _ in range(2):
                    r = self.client.post(
                        f"/exercises/{dead_id}/sets",
                        params={"reps": 5, "weight": weight_dl, "rpe": 8},
                    )
                    self.assertEqual(r.status_code, 200)
                volume_deadlift = 2 * 5 * weight_dl

            expected_volumes[date_str] = round(
                volume_bench + volume_curl + volume_deadlift, 2
            )
            bench_volume_total += volume_bench
            bench_rpe_total += 8 * 3
            bench_sets += 3

        resp = self.client.get(
            "/stats/daily_volume",
            params={"start_date": start.isoformat(), "end_date": end.isoformat()},
        )
        self.assertEqual(resp.status_code, 200)
        data = {d["date"]: d["volume"] for d in resp.json()}
        self.assertEqual(data, expected_volumes)

        resp = self.client.get("/workouts")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 14)

        resp = self.client.get("/stats/equipment_usage")
        self.assertEqual(resp.status_code, 200)
        usage = {d["equipment"]: d["sets"] for d in resp.json()}
        self.assertEqual(usage.get("Adj Dumbbell"), 42)
        self.assertEqual(usage.get("Olympic Barbell"), 42)
        self.assertEqual(usage.get("Hex Bar"), 16)

        resp = self.client.get(
            "/stats/exercise_summary", params={"exercise": "Bench Press"}
        )
        self.assertEqual(resp.status_code, 200)
        summary = resp.json()[0]
        self.assertEqual(summary["sets"], bench_sets)
        self.assertAlmostEqual(summary["volume"], round(bench_volume_total, 2))
        avg_rpe = round(bench_rpe_total / bench_sets, 2)
        self.assertAlmostEqual(summary["avg_rpe"], avg_rpe)
        self.assertAlmostEqual(summary["max_1rm"], round(max_1rm, 2))

        # verify db rows
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM workouts;")
        self.assertEqual(cur.fetchone()[0], 14)
        cur.execute("SELECT COUNT(*) FROM sets;")
        self.assertEqual(cur.fetchone()[0], 100)
        conn.close()


if __name__ == "__main__":
    unittest.main()


class ExtendedUsageTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = "test_longterm_ext.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.api = GymAPI(db_path=self.db_path)
        self.client = TestClient(self.api.app)

    def tearDown(self) -> None:
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_extended_long_term_usage(self) -> None:
        start = datetime.date.today() - datetime.timedelta(days=55)
        end = start + datetime.timedelta(days=55)

        resp = self.client.post(
            "/equipment",
            params={
                "equipment_type": "Free Weights",
                "name": "Adj Dumbbell",
                "muscles": "Biceps Brachii",
            },
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.client.post(
            "/exercise_catalog",
            params={
                "muscle_group": "Arms",
                "name": "Incline Bicep Curl",
                "variants": "",
                "equipment_names": "Adj Dumbbell",
                "primary_muscle": "Biceps Brachii",
            },
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.client.post(
            "/equipment",
            params={
                "equipment_type": "Free Weights",
                "name": "Hex Bar",
                "muscles": "Quadriceps",
            },
        )
        self.assertEqual(resp.status_code, 200)
        resp = self.client.post(
            "/exercise_catalog",
            params={
                "muscle_group": "Legs",
                "name": "Trap Bar Deadlift",
                "variants": "",
                "equipment_names": "Hex Bar",
                "primary_muscle": "Quadriceps",
            },
        )
        self.assertEqual(resp.status_code, 200)

        expected_volumes: dict[str, float] = {}
        bench_volume_total = 0.0
        bench_sets = 0
        bench_rpe_total = 0
        max_1rm = 0.0
        success_count = 0

        for i in range(28):
            w_date = start + datetime.timedelta(days=i * 2)
            date_str = w_date.isoformat()
            reps = 5
            weight = 100.0 + 2 * i
            if i % 5 == 2:
                resp = self.client.post(
                    "/planned_workouts",
                    params={"date": date_str, "training_type": "strength"},
                )
                self.assertEqual(resp.status_code, 200)
                plan_id = resp.json()["id"]
                resp = self.client.post(
                    f"/planned_workouts/{plan_id}/exercises",
                    params={"name": "Bench Press", "equipment": "Olympic Barbell"},
                )
                self.assertEqual(resp.status_code, 200)
                plan_ex = resp.json()["id"]
                resp = self.client.post(
                    f"/planned_exercises/{plan_ex}/sets",
                    params={"reps": reps, "weight": weight, "rpe": 8},
                )
                self.assertEqual(resp.status_code, 200)
                resp = self.client.post(f"/planned_workouts/{plan_id}/use")
                self.assertEqual(resp.status_code, 200)
                workout_id = resp.json()["id"]
                resp = self.client.get(f"/workouts/{workout_id}/exercises")
                bench_id = resp.json()[0]["id"]
                resp_set = self.client.get(f"/exercises/{bench_id}/sets")
                ids = [resp_set.json()[0]["id"]]
            else:
                resp = self.client.post("/workouts", params={"date": date_str})
                self.assertEqual(resp.status_code, 200)
                workout_id = resp.json()["id"]
                resp = self.client.post(
                    f"/workouts/{workout_id}/exercises",
                    params={"name": "Bench Press", "equipment": "Olympic Barbell"},
                )
                self.assertEqual(resp.status_code, 200)
                bench_id = resp.json()["id"]
                resp = self.client.post(
                    f"/exercises/{bench_id}/sets",
                    params={"reps": reps, "weight": weight, "rpe": 8},
                )
                self.assertEqual(resp.status_code, 200)
                ids = [resp.json()["id"]]

            volume_bench = reps * weight
            bench_sets += 1
            bench_rpe_total += 8
            est = MathTools.epley_1rm(weight, reps)
            if est > max_1rm:
                max_1rm = est

            for _ in range(2):
                rec = self.client.post(f"/exercises/{bench_id}/recommend_next")
                if rec.status_code == 200:
                    success_count += 1
                    data = rec.json()
                    volume_bench += data["reps"] * data["weight"]
                    bench_sets += 1
                    bench_rpe_total += data["rpe"]
                    ids.append(data["id"])
                    est = MathTools.epley_1rm(data["weight"], data["reps"])
                    if est > max_1rm:
                        max_1rm = est
                else:
                    r = self.client.post(
                        f"/exercises/{bench_id}/sets",
                        params={"reps": reps, "weight": weight, "rpe": 8},
                    )
                    self.assertEqual(r.status_code, 200)
                    volume_bench += reps * weight
                    bench_sets += 1
                    bench_rpe_total += 8
                    ids.append(r.json()["id"])

            if i % 10 == 3:
                r = self.client.put(
                    f"/sets/{ids[0]}",
                    params={"reps": 6, "weight": weight + 5.0, "rpe": 9},
                )
                self.assertEqual(r.status_code, 200)
                volume_bench += 6 * (weight + 5.0) - reps * weight
                bench_rpe_total += 1
                est = MathTools.epley_1rm(weight + 5.0, 6)
                if est > max_1rm:
                    max_1rm = est

            resp = self.client.post(
                f"/workouts/{workout_id}/exercises",
                params={"name": "Incline Bicep Curl", "equipment": "Adj Dumbbell"},
            )
            self.assertEqual(resp.status_code, 200)
            curl_id = resp.json()["id"]
            curl_weight = 40.0 + i
            for _ in range(3):
                r = self.client.post(
                    f"/exercises/{curl_id}/sets",
                    params={"reps": 8, "weight": curl_weight, "rpe": 7},
                )
                self.assertEqual(r.status_code, 200)
            volume_curl = 3 * 8 * curl_weight

            volume_deadlift = 0.0
            if i >= 6:
                resp = self.client.post(
                    f"/workouts/{workout_id}/exercises",
                    params={"name": "Trap Bar Deadlift", "equipment": "Hex Bar"},
                )
                self.assertEqual(resp.status_code, 200)
                dead_id = resp.json()["id"]
                weight_dl = 150.0 + i
                for _ in range(2):
                    r = self.client.post(
                        f"/exercises/{dead_id}/sets",
                        params={"reps": 5, "weight": weight_dl, "rpe": 8},
                    )
                    self.assertEqual(r.status_code, 200)
                volume_deadlift = 2 * 5 * weight_dl

            expected_volumes[date_str] = round(
                volume_bench + volume_curl + volume_deadlift, 2
            )
            bench_volume_total += volume_bench

        resp = self.client.get(
            "/stats/daily_volume",
            params={"start_date": start.isoformat(), "end_date": end.isoformat()},
        )
        self.assertEqual(resp.status_code, 200)
        data = {d["date"]: d["volume"] for d in resp.json()}
        self.assertEqual(data, expected_volumes)

        resp = self.client.get("/workouts")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 28)

        resp = self.client.get("/stats/equipment_usage")
        self.assertEqual(resp.status_code, 200)
        usage = {d["equipment"]: d["sets"] for d in resp.json()}
        self.assertEqual(usage.get("Adj Dumbbell"), 84)
        self.assertEqual(usage.get("Olympic Barbell"), bench_sets)
        self.assertEqual(usage.get("Hex Bar"), 44)

        resp = self.client.get(
            "/stats/exercise_summary", params={"exercise": "Bench Press"}
        )
        self.assertEqual(resp.status_code, 200)
        summary = resp.json()[0]
        self.assertEqual(summary["sets"], bench_sets)
        self.assertAlmostEqual(summary["volume"], round(bench_volume_total, 2))
        avg_rpe = round(bench_rpe_total / bench_sets, 2)
        self.assertAlmostEqual(summary["avg_rpe"], avg_rpe)
        self.assertAlmostEqual(summary["max_1rm"], round(max_1rm, 2))

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM workouts;")
        self.assertEqual(cur.fetchone()[0], 28)
        cur.execute("SELECT COUNT(*) FROM sets;")
        self.assertEqual(cur.fetchone()[0], 212)
        conn.close()

