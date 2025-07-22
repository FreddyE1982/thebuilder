import os
import sys
import sqlite3
import unittest
from streamlit.testing.v1 import AppTest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))


class StreamlitAppTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = "test_gui.db"
        self.yaml_path = "test_gui_settings.yaml"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        if os.path.exists(self.yaml_path):
            os.remove(self.yaml_path)
        os.environ["DB_PATH"] = self.db_path
        os.environ["YAML_PATH"] = self.yaml_path
        os.environ["TEST_MODE"] = "1"
        self.at = AppTest.from_file("streamlit_app.py", default_timeout=20)
        self.at.query_params["mode"] = "desktop"
        self.at.query_params["tab"] = "workouts"
        self.at.run(timeout=20)

    def tearDown(self) -> None:
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        if os.path.exists(self.yaml_path):
            os.remove(self.yaml_path)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def test_add_workout_and_set(self) -> None:
        self.at.button[1].click().run()
        self.at.selectbox[3].select("Barbell Bench Press").run()
        self.at.selectbox[5].select("Olympic Barbell").run()
        self.at.button[9].click().run()
        self.at.number_input[0].set_value(5).run()
        self.at.number_input[1].set_value(100.0).run()
        self.at.button[13].click().run()

        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM workouts;")
        self.assertEqual(cur.fetchone()[0], 1)
        cur.execute("SELECT name FROM exercises;")
        self.assertEqual(cur.fetchone()[0], "Barbell Bench Press")
        cur.execute("SELECT reps, weight FROM sets;")
        self.assertEqual(cur.fetchone(), (5, 100.0))
        conn.close()

    def test_workout_metadata(self) -> None:
        self.at.button[1].click().run()
        self.at.text_input[1].input("Home").run()
        self.at.button[6].click().run()
        self.at.button[2].click().run()
        self.at.button[3].click().run()

        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT location, start_time, end_time FROM workouts;")
        location, start_time, end_time = cur.fetchone()
        self.assertEqual(location, "Home")
        self.assertIsNotNone(start_time)
        self.assertIsNotNone(end_time)
        conn.close()

    def test_plan_to_workout(self) -> None:
        self.at.date_input[0].set_value("2024-01-02").run()
        self.at.selectbox[0].select("strength").run()
        self.at.button[4].click().run()
        self.at.run()
        self.at.selectbox[0].select("1").run()
        self.at.button[1].click().run()

        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM planned_workouts;")
        self.assertEqual(cur.fetchone()[0], 1)
        cur.execute("SELECT date, training_type FROM workouts;")
        row = cur.fetchone()
        self.assertEqual(row, ("2024-01-02", "strength"))
        conn.close()


if __name__ == "__main__":
    unittest.main()
