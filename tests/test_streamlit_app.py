import os
import sys
import sqlite3
import unittest
import warnings
from altair.utils.deprecation import AltairDeprecationWarning
import yaml

warnings.simplefilter("ignore", AltairDeprecationWarning)

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

    def test_add_favorite_exercise(self) -> None:
        self.at.query_params["tab"] = "library"
        self.at.run()
        self.at.selectbox[6].select("Barbell Bench Press").run()
        self.at.button[5].click().run()

        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT name FROM favorite_exercises;")
        self.assertEqual(cur.fetchone()[0], "Barbell Bench Press")
        conn.close()

    def test_equipment_filtering(self) -> None:
        self.at.query_params["tab"] = "library"
        self.at.run()
        eq_tab = self.at.tabs[4]
        eq_tab.selectbox[0].select("Free Weights").run()
        self.at.run()
        eq_tab = self.at.tabs[4]
        self.assertIn("Olympic Barbell", eq_tab.selectbox[1].options)

    def test_exercise_filtering(self) -> None:
        self.at.query_params["tab"] = "library"
        self.at.run()
        ex_tab = self.at.tabs[5]
        ex_tab.multiselect[0].select("Chest").run()
        self.at.run()
        ex_tab = self.at.tabs[5]
        self.assertIn("Barbell Bench Press", ex_tab.selectbox[2].options)

    def test_custom_exercise_and_logs(self) -> None:
        self.at.query_params["tab"] = "settings"
        self.at.run()
        # Custom exercise
        cust_tab = self.at.tabs[12]
        cust_tab.selectbox[0].select("Back").run()
        cust_tab.text_input[0].input("CustomEx").run()
        cust_tab.text_input[1].input("Var1").run()
        cust_tab.multiselect[0].select("Cable Crossover Machine").run()
        cust_tab.selectbox[1].select("Latissimus Dorsi").run()
        cust_tab.button[0].click().run()
        self.at.run()
        cust_tab = self.at.tabs[12]

        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT muscle_group, name FROM exercise_catalog WHERE name = ?;",
            ("CustomEx",),
        )
        self.assertEqual(cur.fetchone(), ("Back", "CustomEx"))

        # Body weight log
        bw_tab = self.at.tabs[13]
        bw_tab.date_input[0].set_value("2024-01-02").run()
        bw_tab.number_input[0].set_value(80.5).run()
        bw_tab.button[0].click().run()
        self.at.run()
        bw_tab = self.at.tabs[13]
        cur.execute("SELECT weight FROM body_weight_logs;")
        self.assertAlmostEqual(cur.fetchone()[0], 80.5)

        # Wellness log
        well_tab = self.at.tabs[14]
        well_tab.date_input[0].set_value("2024-01-03").run()
        well_tab.number_input[0].set_value(2500.0).run()
        well_tab.number_input[1].set_value(8.0).run()
        well_tab.number_input[2].set_value(5.0).run()
        well_tab.number_input[3].set_value(3).run()
        well_tab.button[0].click().run()
        self.at.run()
        well_tab = self.at.tabs[14]
        cur.execute(
            "SELECT calories, sleep_hours, sleep_quality, stress_level FROM wellness_logs;"
        )
        self.assertEqual(cur.fetchone(), (2500.0, 8.0, 5.0, 3))

        # Tag
        tag_tab = self.at.tabs[15]
        tag_tab.text_input[0].input("morning").run()
        tag_tab.button[0].click().run()
        self.at.run()
        tag_tab = self.at.tabs[15]
        cur.execute("SELECT name FROM tags;")
        self.assertEqual(cur.fetchone()[0], "morning")
        conn.close()

    def test_toggle_theme_button(self) -> None:
        for btn in self.at.button:
            if btn.label == "Toggle Theme":
                btn.click().run()
                break
        with open(self.yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self.assertEqual(data["theme"], "dark")


class StreamlitFullGUITest(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = "test_gui_full.db"
        self.yaml_path = "test_gui_full.yaml"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        if os.path.exists(self.yaml_path):
            os.remove(self.yaml_path)
        os.environ["DB_PATH"] = self.db_path
        os.environ["YAML_PATH"] = self.yaml_path
        os.environ["TEST_MODE"] = "0"
        self.at = AppTest.from_file("streamlit_app.py", default_timeout=20)
        self.at.query_params["mode"] = "desktop"
        self.at.query_params["tab"] = "progress"
        self.at.run(timeout=20)

    def tearDown(self) -> None:
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        if os.path.exists(self.yaml_path):
            os.remove(self.yaml_path)

    def _get_tab(self, label: str):
        for tab in self.at.tabs:
            if tab.label == label:
                return tab
        self.fail(f"Tab {label} not found")

    def test_calendar_tab(self) -> None:
        tab = self._get_tab("Calendar")
        self.assertEqual(tab.header[0].value, "Calendar")

    def test_history_tab(self) -> None:
        tab = self._get_tab("History")
        self.assertEqual(tab.header[0].value, "Workout History")

    def test_dashboard_tab(self) -> None:
        tab = self._get_tab("Dashboard")
        self.assertEqual(tab.header[0].value, "Dashboard")

    def test_stats_tab_subtabs(self) -> None:
        tab = self._get_tab("Exercise Stats")
        self.assertEqual(tab.header[0].value, "Statistics")
        labels = [t.label for t in tab.tabs]
        for name in ["Overview", "Distributions", "Progress", "Records", "Stress Balance"]:
            self.assertIn(name, labels)

    def test_insights_tab(self) -> None:
        tab = self._get_tab("Insights")
        self.assertEqual(tab.header[0].value, "Insights")

    def test_weight_tab(self) -> None:
        tab = self._get_tab("Body Weight")
        self.assertEqual(tab.header[0].value, "Body Weight")

    def test_reports_tab(self) -> None:
        tab = self._get_tab("Reports")
        self.assertEqual(tab.header[0].value, "Reports")

    def test_risk_tab(self) -> None:
        tab = self._get_tab("Risk")
        self.assertEqual(tab.header[0].value, "Risk & Readiness")

    def test_gamification_tab(self) -> None:
        tab = self._get_tab("Gamification")
        self.assertEqual(tab.header[0].value, "Gamification Stats")

    def test_tests_tab(self) -> None:
        tab = self._get_tab("Tests")
        self.assertEqual(tab.header[0].value, "Pyramid Test")

    def test_goals_tab(self) -> None:
        tab = self._get_tab("Goals")
        self.assertEqual(tab.header[0].value, "Goals")


if __name__ == "__main__":
    unittest.main()
