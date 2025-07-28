import os
import sys
import unittest
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from cli import export_workouts, backup_db, restore_db, demo_data
from rest_api import GymAPI
from fastapi.testclient import TestClient

class CLIToolsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = "test_cli.db"
        self.yaml_path = "test_cli.yaml"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        if os.path.exists(self.yaml_path):
            os.remove(self.yaml_path)
        self.api = GymAPI(db_path=self.db_path, yaml_path=self.yaml_path)
        self.client = TestClient(self.api.app)
        self.client.post(
            "/users/register",
            json={"username": "test", "password": "test"},
        )
        login = self.client.post(
            "/token",
            json={"username": "test", "password": "test"},
        )
        token = login.json()["token"]
        self.client.headers.update({"Authorization": token})

    def tearDown(self) -> None:
        for path in [self.db_path, self.yaml_path, "backup.db", "exports"]:
            if os.path.exists(path):
                if os.path.isdir(path):
                    for f in os.listdir(path):
                        os.remove(os.path.join(path, f))
                    os.rmdir(path)
                else:
                    os.remove(path)

    def test_export_backup_restore(self) -> None:
        os.makedirs("exports", exist_ok=True)
        self.client.post("/workouts")
        export_workouts(self.db_path, "csv", "exports")
        self.assertTrue(os.path.exists("exports/workout_1.csv"))
        backup_db(self.db_path, "backup.db")
        self.assertTrue(os.path.exists("backup.db"))
        os.remove(self.db_path)
        restore_db("backup.db", self.db_path)
        self.assertTrue(os.path.exists(self.db_path))

    def test_demo_data(self) -> None:
        demo_data(self.db_path, self.yaml_path)
        api2 = GymAPI(db_path=self.db_path, yaml_path=self.yaml_path)
        workouts = api2.workouts.fetch_all_workouts()
        self.assertEqual(len(workouts), 1)

if __name__ == "__main__":
    unittest.main()
