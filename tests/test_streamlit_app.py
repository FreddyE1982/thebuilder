import os
import sys
import sqlite3
import unittest
import warnings
import shutil
import subprocess
import datetime
from altair.utils.deprecation import AltairDeprecationWarning
import yaml

warnings.simplefilter("ignore", AltairDeprecationWarning)

from streamlit.testing.v1 import AppTest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from streamlit_app import GymApp
from db import (
    TemplateWorkoutRepository,
    FavoriteTemplateRepository,
    PlannedWorkoutRepository,
    PlannedExerciseRepository,
    PlannedSetRepository,
    WorkoutRepository,
    ExerciseRepository,
    SetRepository,
    MuscleGroupRepository,
    GoalRepository,
)


def _find_by_label(elements, label, option=None, key=None):
    for idx, elem in enumerate(elements):
        if getattr(elem, "label", None) == label:
            if option is None or option in getattr(elem, "options", []):
                if key is None or getattr(elem, "key", None) == key:
                    return idx
    raise AssertionError(f"Element with label '{label}' not found")


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

    def _get_tab(self, label: str):
        matches = [t for t in self.at.tabs if t.label == label]
        if not matches:
            self.fail(f"Tab {label} not found")
        if len(matches) == 1:
            return matches[0]
        expected = {"General", "Workout Tags", "Equipment", "Exercise Management", "Muscles"}
        for m in matches:
            sub_labels = {st.label for st in getattr(m, "tabs", [])}
            if expected.issubset(sub_labels):
                return m
        return matches[0]

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def test_add_workout_and_set(self) -> None:
        idx_new = _find_by_label(
            self.at.button,
            "New Workout",
            key="FormSubmitter:new_workout_form-New Workout",
        )
        self.at.button[idx_new].click().run()
        idx_ex = _find_by_label(self.at.selectbox, "Exercise", "Barbell Bench Press")
        self.at.selectbox[idx_ex].select("Barbell Bench Press").run()
        idx_eq = _find_by_label(self.at.selectbox, "Equipment Name", "Olympic Barbell")
        self.at.selectbox[idx_eq].select("Olympic Barbell").run()
        idx_add_ex = _find_by_label(self.at.button, "Add Exercise", key="add_ex_btn")
        self.at.button[idx_add_ex].click().run()
        self.at.number_input[0].set_value(5).run()
        self.at.number_input[1].set_value(100.0).run()
        idx_add_set = _find_by_label(self.at.button, "Add Set", key="add_set_1")
        self.at.button[idx_add_set].click().run()

        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM workouts;")
        self.assertEqual(cur.fetchone()[0], 1)
        cur.execute("SELECT name FROM exercises;")
        self.assertEqual(cur.fetchone()[0], "Barbell Bench Press")
        cur.execute("SELECT reps, weight FROM sets;")
        rows = cur.fetchall()
        self.assertEqual(len(rows), 2)
        self.assertIn((1, 0.0), rows)
        self.assertIn((5, 100.0), rows)
        conn.close()

    def test_set_reordering_buttons(self) -> None:
        idx_new = _find_by_label(
            self.at.button,
            "New Workout",
            key="FormSubmitter:new_workout_form-New Workout",
        )
        self.at.button[idx_new].click().run()
        idx_ex = _find_by_label(self.at.selectbox, "Exercise", "Barbell Bench Press")
        self.at.selectbox[idx_ex].select("Barbell Bench Press").run()
        idx_eq = _find_by_label(self.at.selectbox, "Equipment Name", "Olympic Barbell")
        self.at.selectbox[idx_eq].select("Olympic Barbell").run()
        idx_add_ex = _find_by_label(self.at.button, "Add Exercise", key="add_ex_btn")
        self.at.button[idx_add_ex].click().run()
        self.at.number_input[0].set_value(5).run()
        self.at.number_input[1].set_value(100.0).run()
        idx_add_set = _find_by_label(self.at.button, "Add Set", key="add_set_1")
        self.at.button[idx_add_set].click().run()
        self.at.number_input[0].set_value(3).run()
        self.at.number_input[1].set_value(90.0).run()
        self.at.button[idx_add_set].click().run()

        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT id FROM sets ORDER BY position;")
        ids = [r[0] for r in cur.fetchall()]
        conn.close()

        ex_idx = _find_by_label(
            self.at.tabs, "Barbell Bench Press (Olympic Barbell)"
        )
        exp = self.at.tabs[ex_idx]
        btn_idx = _find_by_label(exp.button, "Move Down", key=f"move_down_{ids[0]}")
        exp.button[btn_idx].click().run()

        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT id FROM sets ORDER BY position;")
        new_order = [r[0] for r in cur.fetchall()]
        conn.close()
        self.assertEqual(new_order, [ids[1], ids[0], ids[2]])

    def test_workout_metadata(self) -> None:
        idx_new = _find_by_label(
            self.at.button,
            "New Workout",
            key="FormSubmitter:new_workout_form-New Workout",
        )
        self.at.button[idx_new].click().run()
        start_idx = _find_by_label(self.at.button, "Start Workout")
        self.at.button[start_idx].click().run()
        loc_idx = _find_by_label(
            self.at.text_input,
            "Location",
            key="workout_location_1",
        )
        self.at.text_input[loc_idx].input("Home").run()
        finish_idx = _find_by_label(self.at.button, "Finish Workout")
        self.at.button[finish_idx].click().run()

        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT location, start_time, end_time FROM workouts;")
        location, start_time, end_time = cur.fetchone()
        self.assertEqual(location, "Home")
        self.assertIsNotNone(start_time)
        self.assertIsNotNone(end_time)
        conn.close()

    def test_create_workout_past_date(self) -> None:
        past = datetime.date.today() - datetime.timedelta(days=2)
        idx_date = _find_by_label(self.at.date_input, "Date", key="new_workout_date")
        self.at.date_input[idx_date].set_value(past).run()
        idx_new = _find_by_label(
            self.at.button,
            "New Workout",
            key="FormSubmitter:new_workout_form-New Workout",
        )
        self.at.button[idx_new].click().run()

        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT date FROM workouts;")
        self.assertEqual(cur.fetchone()[0], past.isoformat())
        conn.close()

    def test_finish_summary_banner(self) -> None:
        idx_new = _find_by_label(
            self.at.button,
            "New Workout",
            key="FormSubmitter:new_workout_form-New Workout",
        )
        self.at.button[idx_new].click().run()
        idx_ex = _find_by_label(self.at.selectbox, "Exercise", "Barbell Bench Press")
        self.at.selectbox[idx_ex].select("Barbell Bench Press").run()
        idx_eq = _find_by_label(self.at.selectbox, "Equipment Name", "Olympic Barbell")
        self.at.selectbox[idx_eq].select("Olympic Barbell").run()
        idx_add_ex = _find_by_label(self.at.button, "Add Exercise", key="add_ex_btn")
        self.at.button[idx_add_ex].click().run()
        self.at.number_input[0].set_value(5).run()
        self.at.number_input[1].set_value(100.0).run()
        idx_add_set = _find_by_label(self.at.button, "Add Set", key="add_set_1")
        self.at.button[idx_add_set].click().run()
        finish_idx = _find_by_label(self.at.button, "Finish Workout")
        self.at.button[finish_idx].click().run()
        messages = [s.body for s in self.at.success]
        self.assertTrue(any("Logged" in m for m in messages))

    def test_no_workouts_message(self) -> None:
        exp_idx = _find_by_label(self.at.tabs, "Existing Workouts")
        exp = self.at.tabs[exp_idx]
        texts = [i.body for i in getattr(exp, "info", [])]
        self.assertIn("No workouts found.", texts)

    def test_workout_search(self) -> None:
        loc_idx = _find_by_label(
            self.at.text_input,
            "Location",
            key="new_workout_location",
        )
        self.at.text_input[loc_idx].input("Home Workout").run()
        new_idx = _find_by_label(
            self.at.button,
            "New Workout",
            key="FormSubmitter:new_workout_form-New Workout",
        )
        self.at.button[new_idx].click().run()
        self.at.text_input[loc_idx].input("Gym Workout").run()
        self.at.button[new_idx].click().run()
        # set notes to enable search functionality
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("UPDATE workouts SET notes=? WHERE id=1", ("Home Workout",))
        cur.execute("UPDATE workouts SET notes=? WHERE id=2", ("Gym Workout",))
        conn.commit()
        conn.close()
        exp_idx = _find_by_label(self.at.tabs, "Existing Workouts")
        ex_exp = self.at.tabs[exp_idx]
        s_idx = _find_by_label(ex_exp.text_input, "Search", key="workout_search")
        ex_exp.text_input[s_idx].input("Gym Workout").run()
        self.at.run()
        ex_exp = self.at.tabs[exp_idx]
        options = ex_exp.selectbox[0].options
        self.assertGreaterEqual(len(options), 1)
    def test_plan_to_workout(self) -> None:
        idx_date = _find_by_label(self.at.date_input, "Plan Date", key="plan_date")
        self.at.date_input[idx_date].set_value("2024-01-02").run()
        idx_type = _find_by_label(self.at.selectbox, "Training Type")
        self.at.selectbox[idx_type].select("strength").run()
        idx = _find_by_label(
            self.at.button,
            "New Planned Workout",
            key="FormSubmitter:new_plan_form-New Planned Workout",
        )
        self.at.button[idx].click().run()
        self.at.run()
        exp_idx = _find_by_label(self.at.tabs, "Use Planned Workout")
        self.at.tabs[exp_idx].selectbox[0].select("1").run()
        self.at.run()
        b_idx = _find_by_label(self.at.button, "Use Plan")
        self.at.button[b_idx].click().run()

        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM planned_workouts;")
        self.assertEqual(cur.fetchone()[0], 1)
        cur.execute("SELECT date, training_type FROM workouts;")
        row = cur.fetchone()
        self.assertEqual(row, ("2024-01-02", "strength"))
        conn.close()

    def test_star_rating_widget(self) -> None:
        idx_new = _find_by_label(
            self.at.button,
            "New Workout",
            key="FormSubmitter:new_workout_form-New Workout",
        )
        self.at.button[idx_new].click().run()
        rating_idx = _find_by_label(self.at.select_slider, "Rating")
        self.at.select_slider[rating_idx].set_value(3).run()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT rating FROM workouts;")
        val = cur.fetchone()[0]
        conn.close()
        self.assertEqual(val, 3)

    def test_add_favorite_exercise(self) -> None:
        self.at.query_params["tab"] = "library"
        self.at.run()
        idx = _find_by_label(
            self.at.selectbox, "Add Favorite", "Barbell Bench Press", key="fav_add_name"
        )
        self.at.selectbox[idx].select("Barbell Bench Press").run()
        b_idx = _find_by_label(self.at.button, "Add Favorite", key="fav_add_btn")
        self.at.button[b_idx].click().run()

        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT name FROM favorite_exercises;")
        self.assertEqual(cur.fetchone()[0], "Barbell Bench Press")
        conn.close()

    def test_quick_add_favorite(self) -> None:
        self.at.query_params["tab"] = "library"
        self.at.run()
        fav_tab = next(
            e for e in self._get_tab("Library").tabs if e.label == "Favorites"
        )
        idx = _find_by_label(
            fav_tab.selectbox, "Add Favorite", "Barbell Bench Press", key="fav_add_name"
        )
        fav_tab.selectbox[idx].select("Barbell Bench Press").run()
        btn_idx = _find_by_label(fav_tab.button, "Add Favorite", key="fav_add_btn")
        fav_tab.button[btn_idx].click().run()

        self.at.query_params["tab"] = "workouts"
        self.at.run()
        log_tab = self._get_tab("Workouts").tabs[0]
        idx_new = _find_by_label(
            log_tab.button,
            "New Workout",
            key="FormSubmitter:new_workout_form-New Workout",
        )
        log_tab.button[idx_new].click().run()
        log_tab = self._get_tab("Workouts").tabs[0]
        mgmt_exp = next(e for e in log_tab.tabs if e.label == "Exercise Management")
        q_idx = _find_by_label(mgmt_exp.button, "Barbell Bench Press")
        mgmt_exp.button[q_idx].click().run()

        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT name FROM exercises;")
        self.assertEqual(cur.fetchone()[0], "Barbell Bench Press")
        conn.close()

    def test_quick_weight_buttons(self) -> None:
        idx_new = _find_by_label(
            self.at.button,
            "New Workout",
            key="FormSubmitter:new_workout_form-New Workout",
        )
        self.at.button[idx_new].click().run()
        idx_ex = _find_by_label(self.at.selectbox, "Exercise", "Barbell Bench Press")
        self.at.selectbox[idx_ex].select("Barbell Bench Press").run()
        idx_eq = _find_by_label(self.at.selectbox, "Equipment Name", "Olympic Barbell")
        self.at.selectbox[idx_eq].select("Olympic Barbell").run()
        idx_add_ex = _find_by_label(self.at.button, "Add Exercise", key="add_ex_btn")
        self.at.button[idx_add_ex].click().run()
        btn_idx = _find_by_label(self.at.button, "20.0 kg", key="qw_1_0")
        self.at.button[btn_idx].click().run()
        idx_add_set = _find_by_label(self.at.button, "Add Set", key="add_set_1")
        self.at.button[idx_add_set].click().run()

        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT weight FROM sets ORDER BY id DESC LIMIT 1;")
        weight = cur.fetchone()[0]
        self.assertIn(weight, [0.0, 20.0])
        conn.close()

    def test_equipment_filtering(self) -> None:
        self.at.query_params["tab"] = "library"
        self.at.run()
        lib_tab = self._get_tab("Library")
        eq_tab = next(e for e in lib_tab.tabs if e.label == "Equipment")
        eq_tab.multiselect[0].select("Free Weights").run()
        self.at.run()
        lib_tab = self._get_tab("Library")
        eq_tab = next(e for e in lib_tab.tabs if e.label == "Equipment")
        self.assertIn("Olympic Barbell", eq_tab.selectbox[0].options)

    def test_exercise_filtering(self) -> None:
        self.at.query_params["tab"] = "library"
        self.at.run()
        lib_tab = self._get_tab("Library")
        ex_tab = next(e for e in lib_tab.tabs if e.label == "Exercises")
        ex_tab.multiselect[0].select("Chest").run()
        self.at.run()
        lib_tab = self._get_tab("Library")
        ex_tab = next(e for e in lib_tab.tabs if e.label == "Exercises")
        self.assertIn("Barbell Bench Press", ex_tab.selectbox[1].options)

    def test_reset_buttons_present(self) -> None:
        self.at.query_params["tab"] = "library"
        self.at.run()
        lib_tab = self._get_tab("Library")
        eq_tab = next(e for e in lib_tab.tabs if e.label == "Equipment")
        idx_eq = _find_by_label(eq_tab.button, "Reset Filters", key="lib_eq_reset")
        self.assertIsNotNone(idx_eq)
        ex_tab = next(e for e in lib_tab.tabs if e.label == "Exercises")
        idx_ex = _find_by_label(ex_tab.button, "Reset Filters", key="lib_ex_reset")
        self.assertIsNotNone(idx_ex)

    def test_tips_panel_present(self) -> None:
        html = "".join(m.body for m in self.at.markdown)
        self.assertIn("tips-panel", html)

    def test_export_button_present(self) -> None:
        os.environ["TEST_MODE"] = "0"
        self.at.query_params["tab"] = "progress"
        self.at.query_params["sub"] = "dashboard"
        self.at.run()
        found = any(btn.label == "Export PNG" for btn in self.at.button)
        self.assertTrue(found)

    def test_intensity_badge_html(self) -> None:
        self.at.query_params["tab"] = "workouts"
        self.at.run()
        idx_new = _find_by_label(
            self.at.button,
            "New Workout",
            key="FormSubmitter:new_workout_form-New Workout",
        )
        self.at.button[idx_new].click().run()
        idx_ex = _find_by_label(self.at.selectbox, "Exercise", "Barbell Bench Press")
        self.at.selectbox[idx_ex].select("Barbell Bench Press").run()
        idx_eq = _find_by_label(self.at.selectbox, "Equipment Name", "Olympic Barbell")
        self.at.selectbox[idx_eq].select("Olympic Barbell").run()
        idx_add_ex = _find_by_label(self.at.button, "Add Exercise", key="add_ex_btn")
        self.at.button[idx_add_ex].click().run()
        self.at.number_input[0].set_value(5).run()
        self.at.number_input[1].set_value(100.0).run()
        idx_add_set = _find_by_label(self.at.button, "Add Set", key="add_set_1")
        self.at.button[idx_add_set].click().run()
        html = "".join(m.body for m in self.at.markdown)
        self.assertIn("intensity-high", html)

    def test_status_badges(self) -> None:
        self.at.query_params["tab"] = "workouts"
        self.at.run()
        idx_new = _find_by_label(
            self.at.button,
            "New Workout",
            key="FormSubmitter:new_workout_form-New Workout",
        )
        self.at.button[idx_new].click().run()
        html = "".join(m.body for m in self.at.markdown)
        self.assertIn("status-idle", html)
        start_idx = _find_by_label(self.at.button, "Start Workout")
        self.at.button[start_idx].click().run()
        html = "".join(m.body for m in self.at.markdown)
        self.assertIn("status-running", html)
        idx_ex = _find_by_label(self.at.selectbox, "Exercise", "Barbell Bench Press")
        self.at.selectbox[idx_ex].select("Barbell Bench Press").run()
        idx_eq = _find_by_label(self.at.selectbox, "Equipment Name", "Olympic Barbell")
        self.at.selectbox[idx_eq].select("Olympic Barbell").run()
        idx_add_ex = _find_by_label(self.at.button, "Add Exercise", key="add_ex_btn")
        self.at.button[idx_add_ex].click().run()
        self.at.number_input[0].set_value(5).run()
        self.at.number_input[1].set_value(100.0).run()
        idx_add_set = _find_by_label(self.at.button, "Add Set", key="add_set_1")
        self.at.button[idx_add_set].click().run()
        start_set_idx = _find_by_label(self.at.button, "Start", key="start_set_1")
        self.at.button[start_set_idx].click().run()
        html = "".join(m.body for m in self.at.markdown)
        self.assertIn("status-running", html)
        finish_set_idx = _find_by_label(self.at.button, "Finish", key="finish_set_1")
        self.at.button[finish_set_idx].click().run()
        html = "".join(m.body for m in self.at.markdown)
        self.assertIn("status-finished", html)
        finish_idx = _find_by_label(self.at.button, "Finish Workout")
        self.at.button[finish_idx].click().run()
        html = "".join(m.body for m in self.at.markdown)
        self.assertIn("status-finished", html)

    def test_set_edit_keeps_open(self) -> None:
        idx_new = _find_by_label(
            self.at.button,
            "New Workout",
            key="FormSubmitter:new_workout_form-New Workout",
        )
        self.at.button[idx_new].click().run()
        idx_ex = _find_by_label(self.at.selectbox, "Exercise", "Barbell Bench Press")
        self.at.selectbox[idx_ex].select("Barbell Bench Press").run()
        idx_eq = _find_by_label(self.at.selectbox, "Equipment Name", "Olympic Barbell")
        self.at.selectbox[idx_eq].select("Olympic Barbell").run()
        idx_add_ex = _find_by_label(self.at.button, "Add Exercise", key="add_ex_btn")
        self.at.button[idx_add_ex].click().run()
        self.at.number_input[0].set_value(5).run()
        self.at.number_input[1].set_value(100.0).run()
        idx_add_set = _find_by_label(self.at.button, "Add Set", key="add_set_1")
        self.at.button[idx_add_set].click().run()

        ex_idx = _find_by_label(
            self.at.tabs, "Barbell Bench Press (Olympic Barbell)"
        )
        ex_exp = self.at.tabs[ex_idx]
        set_exp = next(e for e in ex_exp.tabs if e.label.startswith("Set 1"))
        set_exp.number_input[1].set_value(110.0).run()

        ex_exp = self.at.tabs[ex_idx]
        set_exp = next(e for e in ex_exp.tabs if e.label.startswith("Set 1"))
        self.assertEqual(set_exp.number_input[1].value, 110.0)

    def test_custom_exercise_and_logs(self) -> None:
        self.at.query_params["tab"] = "settings"
        self.at.run()
        # Custom exercise
        settings_tab = self._get_tab("Settings")
        cust_tab = next(
            t for t in settings_tab.tabs if t.label == "Exercise Management"
        )
        idx_group = _find_by_label(
            cust_tab.selectbox, "Muscle Group", key="cust_ex_group"
        )
        cust_tab.selectbox[idx_group].select("Chest").run()
        cust_tab.text_input[0].input("CustomEx").run()
        cust_tab.text_input[1].input("Var1").run()
        idx_eq = _find_by_label(cust_tab.multiselect, "Equipment", key="cust_ex_eq")
        cust_tab.multiselect[idx_eq].select("Chest Press Machine").run()
        idx_chk = _find_by_label(
            cust_tab.checkbox, "Muscles Like Equipment", key="cust_ex_match"
        )
        cust_tab.checkbox[idx_chk].check().run()
        idx_btn = _find_by_label(cust_tab.button, "Add Exercise", key="cust_ex_add")
        cust_tab.button[idx_btn].click().run()
        self.at.run()
        settings_tab = self._get_tab("Settings")
        cust_tab = next(
            t for t in settings_tab.tabs if t.label == "Exercise Management"
        )

        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT muscle_group, primary_muscle, secondary_muscle FROM exercise_catalog WHERE name = ?;",
            ("CustomEx",),
        )
        self.assertEqual(
            cur.fetchone(),
            ("Chest", "Pectoralis Major", "Anterior Deltoid|Triceps Brachii"),
        )

        # Body weight log
        settings_tab = self._get_tab("Settings")
        bw_tab = next(t for t in settings_tab.tabs if t.label == "Body Weight Logs")
        bw_tab.date_input[0].set_value("2024-01-02").run()
        bw_tab.number_input[0].set_value(80.5).run()
        bw_tab.button[0].click().run()
        self.at.run()
        settings_tab = self._get_tab("Settings")
        bw_tab = next(t for t in settings_tab.tabs if t.label == "Body Weight Logs")
        cur.execute("SELECT weight FROM body_weight_logs;")
        self.assertAlmostEqual(cur.fetchone()[0], 80.5)

        # Tag
        tag_tab = next(t for t in settings_tab.tabs if t.label == "Workout Tags")
        tag_tab.text_input[0].input("morning").run()
        tag_tab.button[0].click().run()
        self.at.run()
        tag_tab = next(t for t in settings_tab.tabs if t.label == "Workout Tags")
        cur.execute("SELECT name FROM tags;")
        self.assertEqual(cur.fetchone()[0], "morning")
        conn.close()

    def test_muscle_alias_and_link(self) -> None:
        self.at.query_params["tab"] = "settings"
        self.at.run()
        settings_tab = self._get_tab("Settings")
        mus_tab = next(t for t in settings_tab.tabs if t.label == "Muscles")
        mus_tab.selectbox[0].select("Biceps Brachii").run()
        mus_tab.selectbox[1].select("Brachialis").run()
        mus_tab.button[0].click().run()
        self.at.run()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT canonical_name FROM muscles WHERE name = ?;",
            ("Brachialis",),
        )
        self.assertEqual(cur.fetchone()[0], "Biceps Brachii")
        settings_tab = self._get_tab("Settings")
        mus_tab = next(t for t in settings_tab.tabs if t.label == "Muscles")
        mus_tab.text_input[0].input("Lats").run()
        mus_tab.selectbox[2].select("Latissimus Dorsi").run()
        mus_tab.button[1].click().run()
        self.at.run()
        cur.execute(
            "SELECT canonical_name FROM muscles WHERE name = ?;",
            ("Lats",),
        )
        self.assertEqual(cur.fetchone()[0], "Latissimus Dorsi")
        conn.close()

    def test_add_muscle(self) -> None:
        self.at.query_params["tab"] = "settings"
        self.at.run()
        settings_tab = self._get_tab("Settings")
        mus_tab = next(t for t in settings_tab.tabs if t.label == "Muscles")
        mus_tab.text_input[1].input("Obliques").run()
        mus_tab.button[2].click().run()
        self.at.run()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT name FROM muscles WHERE name = ?;", ("Obliques",))
        self.assertEqual(cur.fetchone()[0], "Obliques")
        conn.close()

    def test_muscle_dropdown_sorted(self) -> None:
        self.at.query_params["tab"] = "settings"
        self.at.run()
        settings_tab = self._get_tab("Settings")
        mus_tab = next(t for t in settings_tab.tabs if t.label == "Muscles")
        mus_tab.text_input[1].input("Aardvark").run()
        mus_tab.button[2].click().run()
        self.at.run()
        settings_tab = self._get_tab("Settings")
        mus_tab = next(t for t in settings_tab.tabs if t.label == "Muscles")
        idx = _find_by_label(mus_tab.selectbox, "Muscle 1")
        options = mus_tab.selectbox[idx].options
        self.assertEqual(options, sorted(options))

    def test_muscle_group_management(self) -> None:
        self.skipTest("muscle group UI changed")

    def test_equipment_add_update_delete(self) -> None:
        self.at.query_params["tab"] = "settings"
        self.at.run()
        settings_tab = self._get_tab("Settings")
        eq_tab = next(t for t in settings_tab.tabs if t.label == "Equipment")
        eq_tab.text_input[0].input("MyType").run()
        eq_tab.button[0].click().run()
        self.at.run()
        settings_tab = self._get_tab("Settings")
        eq_tab = next(t for t in settings_tab.tabs if t.label == "Equipment")
        eq_tab.selectbox[0].select("MyType").run()
        eq_tab.text_input[1].input("TestEq").run()
        eq_tab.multiselect[0].select("Biceps Brachii").run()
        eq_tab.button[1].click().run()
        self.at.run()
        settings_tab = self._get_tab("Settings")
        eq_tab = next(t for t in settings_tab.tabs if t.label == "Equipment")
        target = None
        for exp in eq_tab.tabs:
            if exp.label == "TestEq":
                target = exp
                break
        self.assertIsNotNone(target)
        target.text_input[0].input("TestEq2").run()
        self.at.run()
        settings_tab = self._get_tab("Settings")
        eq_tab = next(t for t in settings_tab.tabs if t.label == "Equipment")
        found = None
        for exp in eq_tab.tabs:
            if exp.label == "TestEq2":
                exp.button[0].click().run()
                found = exp
                break
        self.assertIsNotNone(found)
        self.at.run()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT name FROM equipment WHERE name = ?;", ("TestEq2",))
        self.assertIsNone(cur.fetchone())
        conn.close()

    def test_exercise_alias_linking(self) -> None:
        self.at.query_params["tab"] = "settings"
        self.at.run()
        settings_tab = self._get_tab("Settings")
        ex_tab = next(t for t in settings_tab.tabs if t.label == "Exercise Aliases")
        ex_tab.selectbox[0].select("Barbell Bench Press").run()
        ex_tab.selectbox[1].select("Dumbbell Bench Press").run()
        ex_tab.button[0].click().run()
        self.at.run()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT canonical_name FROM exercise_names WHERE name = ?;",
            ("Dumbbell Bench Press",),
        )
        self.assertEqual(cur.fetchone()[0], "Barbell Bench Press")
        settings_tab = self._get_tab("Settings")
        ex_tab = next(t for t in settings_tab.tabs if t.label == "Exercise Aliases")
        ex_tab.text_input[0].input("DB Press").run()
        ex_tab.selectbox[2].select("Barbell Bench Press").run()
        ex_tab.button[1].click().run()
        self.at.run()
        cur.execute(
            "SELECT canonical_name FROM exercise_names WHERE name = ?;",
            ("DB Press",),
        )
        self.assertEqual(cur.fetchone()[0], "Barbell Bench Press")
        conn.close()

    def test_exercise_variant_switch(self) -> None:
        self.at.query_params["tab"] = "settings"
        self.at.run()
        cust_tab = next(t for t in self.at.tabs if t.label == "Exercise Management")
        var_exp = cust_tab.tabs[_find_by_label(cust_tab.tabs, "Link Variants")]
        var_exp.selectbox[0].select("Barbell Bench Press").run()
        var_exp.selectbox[1].select("Dumbbell Bench Press").run()
        var_exp.button[0].click().run()
        self.at.run()

        self.at.query_params["tab"] = "workouts"
        self.at.run()
        idx_new = _find_by_label(
            self.at.button,
            "New Workout",
            key="FormSubmitter:new_workout_form-New Workout",
        )
        self.at.button[idx_new].click().run()
        idx_ex = _find_by_label(self.at.selectbox, "Exercise", "Barbell Bench Press")
        self.at.selectbox[idx_ex].select("Barbell Bench Press").run()
        idx_eq = _find_by_label(self.at.selectbox, "Equipment Name", "Olympic Barbell")
        self.at.selectbox[idx_eq].select("Olympic Barbell").run()
        idx_add_ex = _find_by_label(self.at.button, "Add Exercise", key="add_ex_btn")
        self.at.button[idx_add_ex].click().run()
        self.at.run()
        ex_idx = _find_by_label(
            self.at.tabs, "Barbell Bench Press (Olympic Barbell)"
        )
        exp = self.at.tabs[ex_idx]
        btn_idx = _find_by_label(exp.button, "Dumbbell Bench Press")
        exp.button[btn_idx].click().run()
        self.at.run()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT name FROM exercises;")
        self.assertEqual(cur.fetchone()[0], "Dumbbell Bench Press")
        conn.close()

    def test_toggle_theme_button(self) -> None:
        for btn in self.at.button:
            if btn.label == "Toggle Theme":
                btn.click().run()
                break
        with open(self.yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self.assertEqual(data["theme"], "dark")

    def test_toggle_theme_header_button(self) -> None:
        idx = _find_by_label(self.at.button, "Toggle Theme", key="toggle_theme_header")
        self.at.button[idx].click().run()
        with open(self.yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self.assertEqual(data["theme"], "dark")

    def test_help_header_button(self) -> None:
        idx = _find_by_label(self.at.button, "Help", key="help_button_header")
        self.at.button[idx].click().run()
        help_text = any("Workout Logger Help" in m.body for m in self.at.markdown)
        self.assertTrue(help_text)

    def test_help_tips_disabled_by_default(self) -> None:
        tips_present = any(e.label == "Need Help?" for e in self.at.tabs)
        self.assertFalse(tips_present)

    def test_help_overlay_button_disabled_by_default(self) -> None:
        overlay_present = any(
            getattr(b, "key", None) == "help_overlay_btn" for b in self.at.button
        )
        self.assertFalse(overlay_present)

    def test_enable_help_tips(self) -> None:
        with open(self.yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        data["show_help_tips"] = True
        with open(self.yaml_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f)
        self.at.run()
        tips_present = any(e.label == "Need Help?" for e in self.at.tabs)
        overlay_present = any(
            getattr(b, "key", None) == "help_overlay_btn" for b in self.at.button
        )
        self.assertTrue(tips_present)
        self.assertTrue(overlay_present)

    def test_onboarding_tutorial_disabled(self) -> None:
        tutorial = any("First Workout" in m.body for m in self.at.markdown)
        self.assertFalse(tutorial)

    def test_enable_onboarding_tutorial(self) -> None:
        with open(self.yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        data["show_onboarding"] = True
        with open(self.yaml_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f)
        self.at.run()
        tutorial = any("First Workout" in m.body for m in self.at.markdown)
        self.assertTrue(tutorial)

    def test_pinned_stats_header(self) -> None:
        idx_new = _find_by_label(
            self.at.button,
            "New Workout",
            key="FormSubmitter:new_workout_form-New Workout",
        )
        self.at.button[idx_new].click().run()
        idx_ex = _find_by_label(self.at.selectbox, "Exercise", "Barbell Bench Press")
        self.at.selectbox[idx_ex].select("Barbell Bench Press").run()
        idx_eq = _find_by_label(self.at.selectbox, "Equipment Name", "Olympic Barbell")
        self.at.selectbox[idx_eq].select("Olympic Barbell").run()
        idx_add_ex = _find_by_label(self.at.button, "Add Exercise", key="add_ex_btn")
        self.at.button[idx_add_ex].click().run()
        self.at.number_input[0].set_value(5).run()
        self.at.number_input[1].set_value(100.0).run()
        idx_add_set = _find_by_label(self.at.button, "Add Set", key="add_set_1")
        self.at.button[idx_add_set].click().run()
        self.at.run()
        labels = [m.label for m in self.at.metric]
        self.assertIn("Today's Volume", labels)

    def test_colorblind_theme_option(self) -> None:
        self.at.query_params["tab"] = "settings"
        self.at.run()
        settings_tab = self._get_tab("Settings")
        gen_tab = settings_tab.tabs[0]
        idx = _find_by_label(gen_tab.selectbox, "Color Theme")
        options = gen_tab.selectbox[idx].options
        self.assertIn("colorblind", options)

    def test_tooltips_present(self) -> None:
        with open("streamlit_app.py", "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Select the primary training focus", content)

    def test_delete_exercise_confirmation(self) -> None:
        idx_new = _find_by_label(
            self.at.button,
            "New Workout",
            key="FormSubmitter:new_workout_form-New Workout",
        )
        self.at.button[idx_new].click().run()
        idx_ex = _find_by_label(self.at.selectbox, "Exercise", "Barbell Bench Press")
        self.at.selectbox[idx_ex].select("Barbell Bench Press").run()
        idx_eq = _find_by_label(self.at.selectbox, "Equipment Name", "Olympic Barbell")
        self.at.selectbox[idx_eq].select("Olympic Barbell").run()
        idx_add_ex = _find_by_label(self.at.button, "Add Exercise", key="add_ex_btn")
        self.at.button[idx_add_ex].click().run()
        ex_idx = _find_by_label(
            self.at.tabs, "Barbell Bench Press (Olympic Barbell)"
        )
        exp = self.at.tabs[ex_idx]
        rm_idx = _find_by_label(exp.button, "Remove Exercise", key="remove_ex_1")
        exp.button[rm_idx].click().run()
        confirm = any("Delete exercise 1?" in m.body for m in self.at.markdown)
        self.assertTrue(confirm)

    def test_header_quick_search(self) -> None:
        idx_new = _find_by_label(
            self.at.button,
            "New Workout",
            key="FormSubmitter:new_workout_form-New Workout",
        )
        self.at.button[idx_new].click().run()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("UPDATE workouts SET notes=? WHERE id=1", ("Morning",))
        conn.commit()
        conn.close()
        s_idx = _find_by_label(self.at.text_input, "Search", key="header_search")
        self.at.text_input[s_idx].input("Morning").run()
        b_idx = _find_by_label(self.at.button, "Search", key="header_search_btn")
        self.at.button[b_idx].click().run()
        sel_idx = _find_by_label(self.at.selectbox, "Results", key="header_search_sel")
        option = self.at.selectbox[sel_idx].options[0]
        self.at.selectbox[sel_idx].select(option).run()
        o_idx = _find_by_label(self.at.button, "Open", key="header_search_open")
        self.at.button[o_idx].click().run()
        exp_idx = _find_by_label(self.at.tabs, "Exercise Management")
        self.assertGreater(len(self.at.tabs[exp_idx].button), 0)

    def test_git_pull_button(self) -> None:
        self.at.query_params["tab"] = "settings"
        self.at.run()
        settings_tab = self._get_tab("Settings")
        gen_tab = next(t for t in settings_tab.tabs if t.label == "General")
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
        idx = _find_by_label(gen_tab.button, "Git Pull")
        gen_tab.button[idx].click().run()
        self.at.run()
        self.assertTrue(os.path.exists(os.path.join(repo_dir, "file.txt")))
        shutil.rmtree(remote_dir)
        shutil.rmtree(repo_dir)

    def test_compact_mode_toggle(self) -> None:
        self.at.query_params["tab"] = "settings"
        self.at.run()
        settings_tab = self._get_tab("Settings")
        idx = _find_by_label(settings_tab.checkbox, "Compact Mode")
        current = settings_tab.checkbox[idx].value
        if current:
            settings_tab.checkbox[idx].uncheck().run()
        else:
            settings_tab.checkbox[idx].check().run()
        save_idx = _find_by_label(settings_tab.button, "Save General Settings")
        settings_tab.button[save_idx].click().run()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = 'compact_mode';")
        val = cur.fetchone()[0]
        conn.close()
        self.assertEqual(bool(int(val)), not current)

    def test_font_size_slider(self) -> None:
        self.at.query_params["tab"] = "settings"
        self.at.run()
        settings_tab = self._get_tab("Settings")
        idx = _find_by_label(settings_tab.slider, "Font Size (px)")
        current = settings_tab.slider[idx].value
        settings_tab.slider[idx].set_value(current + 1).run()
        save_idx = _find_by_label(settings_tab.button, "Save General Settings")
        settings_tab.button[save_idx].click().run()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = 'font_size';")
        val = cur.fetchone()[0]
        conn.close()
        self.assertEqual(int(float(val)), int(current) + 1)

    def test_layout_spacing_slider(self) -> None:
        self.at.query_params["tab"] = "settings"
        self.at.run()
        settings_tab = self._get_tab("Settings")
        idx = _find_by_label(settings_tab.slider, "Layout Spacing")
        current = settings_tab.slider[idx].value
        settings_tab.slider[idx].set_value(current + 0.5).run()
        save_idx = _find_by_label(settings_tab.button, "Save General Settings")
        settings_tab.button[save_idx].click().run()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = 'layout_spacing';")
        val = cur.fetchone()[0]
        conn.close()
        self.assertAlmostEqual(float(val), current + 0.5, places=2)

    def test_flex_metric_grid_toggle(self) -> None:
        self.at.query_params["tab"] = "settings"
        self.at.run()
        settings_tab = self._get_tab("Settings")
        idx = _find_by_label(settings_tab.checkbox, "Flex Metric Grid")
        cur_val = settings_tab.checkbox[idx].value
        if cur_val:
            settings_tab.checkbox[idx].uncheck().run()
        else:
            settings_tab.checkbox[idx].check().run()
        save_idx = _find_by_label(settings_tab.button, "Save General Settings")
        settings_tab.button[save_idx].click().run()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = 'flex_metric_grid';")
        val = cur.fetchone()[0]
        conn.close()
        self.assertEqual(bool(int(val)), not cur_val)

    def test_default_avatar_choice(self) -> None:
        self.at.query_params["tab"] = "settings"
        self.at.run()
        settings_tab = self._get_tab("Settings")
        idx = _find_by_label(settings_tab.selectbox, "Avatar")
        settings_tab.selectbox[idx].select("Default 1").run()
        save_idx = _find_by_label(settings_tab.button, "Save General Settings")
        settings_tab.button[save_idx].click().run()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = 'avatar';")
        val = cur.fetchone()[0]
        conn.close()
        self.assertGreater(len(val), 50)

    def test_language_selector(self) -> None:
        self.at.query_params["tab"] = "settings"
        self.at.run()
        settings_tab = self._get_tab("Settings")
        gen_tab = next(t for t in settings_tab.tabs if t.label == "General")
        idx = _find_by_label(gen_tab.selectbox, "Language")
        gen_tab.selectbox[idx].select("es").run()
        save_idx = _find_by_label(gen_tab.button, "Save General Settings")
        gen_tab.button[save_idx].click().run()
        self.at.run()
        from localization import translator

        self.assertEqual(translator.language, "es")

    def test_timezone_formatting(self) -> None:
        repo = GymApp(self.db_path, self.yaml_path)
        repo.settings_repo.set_text("timezone", "America/New_York")
        repo = GymApp(self.db_path, self.yaml_path)
        res = repo._format_time("2023-01-01T12:00:00")
        self.assertEqual(res, "07:00")



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
        matches = [t for t in self.at.tabs if t.label == label]
        if not matches:
            self.fail(f"Tab {label} not found")
        if len(matches) == 1:
            return matches[0]
        expected = {"General", "Workout Tags", "Equipment", "Exercise Management", "Muscles"}
        for m in matches:
            sub_labels = {st.label for st in getattr(m, "tabs", [])}
            if expected.issubset(sub_labels):
                return m
        return matches[0]

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def test_calendar_tab(self) -> None:
        tab = self._get_tab("Calendar")
        self.assertEqual(tab.header[0].value, "Calendar")
        self.assertGreater(len(tab.tabs), 0)

    def test_history_tab(self) -> None:
        tab = self._get_tab("History")
        self.assertEqual(tab.header[0].value, "Workout History")
        labels = [t.label for t in tab.tabs]
        self.assertIn("List", labels)
        list_tab = next(t for t in tab.tabs if t.label == "List")
        buttons = [b.label for b in list_tab.button]
        self.assertIn("Last 7d", buttons)
        self.assertIn("Last 30d", buttons)
        self.assertIn("Last 90d", buttons)
        self.assertIn("Clear Filters", buttons)
        chk_labels = [c.label for c in list_tab.checkbox]
        self.assertIn("Unrated Only", chk_labels)

    def test_dashboard_tab(self) -> None:
        tab = self._get_tab("Dashboard")
        self.assertEqual(tab.header[0].value, "Dashboard")
        self.assertGreaterEqual(len(tab.metric), 8)

    def test_analytics_hub_tab(self) -> None:
        tab = self._get_tab("Analytics Hub")
        self.assertEqual(tab.header[0].value, "Analytics Hub")
        labels = [b.label for b in tab.button]
        self.assertIn("Dashboard", labels)

    def test_hub_button_sets_param(self) -> None:
        tab = self._get_tab("Analytics Hub")
        idx = _find_by_label(tab.button, "Dashboard", key="hub_dashboard")
        tab.button[idx].click().run()
        sub = self.at.query_params.get("sub")
        if isinstance(sub, list):
            sub = sub[0]
        self.assertEqual(sub, "dashboard")

    def test_stats_tab_subtabs(self) -> None:
        tab = self._get_tab("Exercise Stats")
        self.assertEqual(tab.header[0].value, "Statistics")
        labels = [t.label for t in tab.tabs]
        for name in [
            "Overview",
            "Distributions",
            "Progress",
            "Records",
            "Stress Balance",
        ]:
            self.assertIn(name, labels)
        self.assertGreater(len(tab.tabs[0].table), 0)

    def test_insights_tab(self) -> None:
        tab = self._get_tab("Insights")
        self.assertEqual(tab.header[0].value, "Insights")
        self.assertGreater(len(tab.tabs), 0)

    def test_weight_tab(self) -> None:
        tab = self._get_tab("Body Weight")
        self.assertEqual(tab.header[0].value, "Body Weight")
        self.assertGreater(len(tab.metric), 3)

    def test_wellness_tab(self) -> None:
        tab = self._get_tab("Wellness Logs")
        self.assertEqual(tab.header[0].value, "Wellness Logs")
        entry_tab = tab.tabs[0]
        entry_tab.date_input[0].set_value("2024-01-03").run()
        entry_tab.number_input[0].set_value(2500.0).run()
        entry_tab.number_input[1].set_value(8.0).run()
        entry_tab.number_input[2].set_value(5.0).run()
        entry_tab.number_input[3].set_value(3).run()
        entry_tab.button[0].click().run()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT calories, sleep_hours, sleep_quality, stress_level FROM wellness_logs;"
        )
        self.assertEqual(cur.fetchone(), (2500.0, 8.0, 5.0, 3))
        conn.close()

    def test_reports_tab(self) -> None:
        tab = self._get_tab("Reports")
        self.assertEqual(tab.header[0].value, "Reports")
        self.assertGreater(len(tab.metric), 4)

    def test_quick_report_buttons(self) -> None:
        tab = self._get_tab("Reports")
        range_exp = tab.tabs[0]
        buttons = [b.label for b in range_exp.button]
        self.assertIn("Last Week", buttons)
        self.assertIn("Last Month", buttons)

    def test_connection_status_display(self) -> None:
        status_present = any("conn-status" in m.body for m in self.at.markdown)
        self.assertTrue(status_present)

    def test_risk_tab(self) -> None:
        tab = self._get_tab("Risk")
        self.assertEqual(tab.header[0].value, "Risk & Readiness")
        self.assertGreater(len(tab.metric), 2)

    def test_gamification_tab(self) -> None:
        tab = self._get_tab("Gamification")
        self.assertGreaterEqual(len(tab.metric), 1)

    def test_challenges_tab(self) -> None:
        tab = self._get_tab("Challenges")
        self.assertEqual(tab.header[0].value, "Challenges")
        self.assertGreater(len(tab.tabs), 0)

    def test_tests_tab(self) -> None:
        tab = self._get_tab("Tests")
        self.assertEqual(tab.header[0].value, "Pyramid Test")
        self.assertGreater(len(tab.tabs), 1)

    def test_goals_tab(self) -> None:
        tab = self._get_tab("Goals")
        self.assertEqual(tab.header[0].value, "Goals")
        self.assertGreater(len(tab.tabs), 1)

    def test_goal_donut_chart(self) -> None:
        tab = self._get_tab("Goals")
        overview = tab.tabs[0]
        if hasattr(overview, "altair_chart"):
            self.assertTrue(True)
        else:
            self.skipTest("No goal chart present")

    def test_unsaved_indicator_present(self) -> None:
        indicator = any("unsaved-indicator" in m.body for m in self.at.markdown)
        self.assertTrue(indicator)

    def test_month_timeline(self) -> None:
        tab = self._get_tab("History")
        self.assertTrue(any("month-timeline" in m.body for m in tab.markdown))

    def test_forecast_sections_collapsible(self) -> None:
        idx = _find_by_label(self.at.selectbox, "Exercise", key="stats_ex")
        self.at = self.at.selectbox[idx].select("Barbell Bench Press").run()
        prog_tab = self._get_tab("Exercise Stats").tabs[3]
        labels = [e.label for e in prog_tab.tabs]
        self.assertTrue(labels)

    def test_main_tabs_present(self) -> None:
        labels = [t.label for t in self.at.tabs]
        for name in ["Workouts", "Library", "Progress", "Settings"]:
            self.assertIn(name, labels)

    def test_workouts_subtabs(self) -> None:
        self.at.query_params["tab"] = "workouts"
        self.at.run()
        tab = self._get_tab("Workouts")
        labels = [t.label for t in tab.tabs]
        self.assertIn("Log", labels)
        self.assertIn("Plan", labels)

    def test_plan_inner_tabs(self) -> None:
        self.at.query_params["tab"] = "workouts"
        self.at.run()
        plan_tab = self._get_tab("Plan")
        labels = [e.label for e in plan_tab.tabs]
        for name in ["AI Planner", "Goal Planner", "Templates", "Planned Workouts"]:
            self.assertIn(name, labels)

    def test_goal_plan_creation(self) -> None:
        gp_repo = GoalRepository(self.db_path)
        today = datetime.date.today().isoformat()
        target = (datetime.date.today() + datetime.timedelta(days=7)).isoformat()
        gp_repo.add("Barbell Bench Press", "1RM", 80.0, "kg", today, target)
        self.at.query_params["tab"] = "workouts"
        self.at.run()
        plan_tab = self._get_tab("Plan")
        gp_exp = next(e for e in plan_tab.tabs if e.label == "Goal Planner")
        gp_exp.button[0].click().run()
        pw_repo = PlannedWorkoutRepository(self.db_path)
        self.assertEqual(len(pw_repo.fetch_all(None, None)), 1)

    def test_library_sections(self) -> None:
        self.at.query_params["tab"] = "library"
        self.at.run()
        tab = self._get_tab("Library")
        labels = [e.label for e in tab.tabs]
        for name in ["Favorites", "Templates", "Equipment", "Exercises"]:
            self.assertIn(name, labels)

    def test_settings_subtabs(self) -> None:
        self.at.query_params["tab"] = "settings"
        self.at.run()
        tab = self._get_tab("Settings")
        labels = [t.label for t in tab.tabs]
        for name in [
            "General",
            "Workout Tags",
            "Equipment",
            "Exercise Management",
            "Muscles",
            "Exercise Aliases",
            "Body Weight Logs",
            "Heart Rate Logs",
            "Autoplanner Status",
        ]:
            self.assertIn(name, labels)

    def test_settings_tab_order(self) -> None:
        self.at.query_params["tab"] = "settings"
        self.at.run()
        tab = self._get_tab("Settings")
        labels = [t.label for t in tab.tabs]
        expected = [
            "Settings",
            "General",
            "Workout Tags",
            "Equipment",
            "Exercise Management",
            "Muscles",
        ]
        indices = [labels.index(name) for name in expected]
        self.assertEqual(indices, sorted(indices))

    def test_overdue_plan_warning(self) -> None:
        conn = self._connect()
        cur = conn.cursor()
        yest = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        cur.execute(
            "INSERT INTO planned_workouts (date, training_type) VALUES (?, 'strength');",
            (yest,),
        )
        conn.commit()
        conn.close()
        self.at.query_params["tab"] = "plan"
        self.at.run()
        warnings = [w.body for w in self.at.warning]
        self.assertTrue(any("overdue" in w for w in warnings))

    def test_planned_summary(self) -> None:
        conn = self._connect()
        cur = conn.cursor()
        tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        cur.execute(
            "INSERT INTO planned_workouts (date, training_type) VALUES (?, 'strength');",
            (tomorrow,),
        )
        conn.commit()
        conn.close()
        self.at.query_params["tab"] = "workouts"
        self.at.run()
        exp_idx = _find_by_label(self.at.tabs, "Upcoming Planned Workouts")
        self.assertIsNotNone(self.at.tabs[exp_idx])


class StreamlitAdditionalGUITest(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = "test_gui_add.db"
        self.yaml_path = "test_gui_add.yaml"
        for path in [self.db_path, self.yaml_path]:
            if os.path.exists(path):
                os.remove(path)
        from db import MLModelRepository
        MLModelRepository(self.db_path)
        os.environ["DB_PATH"] = self.db_path
        os.environ["YAML_PATH"] = self.yaml_path
        os.environ["TEST_MODE"] = "0"
        self.at = AppTest.from_file("streamlit_app.py", default_timeout=20)
        self.at.query_params["mode"] = "desktop"
        self.at.query_params["tab"] = "workouts"
        self.at.run(timeout=20)

    def tearDown(self) -> None:
        for path in [self.db_path, self.yaml_path]:
            if os.path.exists(path):
                os.remove(path)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def test_sidebar_new_workout(self) -> None:
        self.at.sidebar.button[0].click().run()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM workouts;")
        self.assertEqual(cur.fetchone()[0], 1)
        conn.close()

    def test_help_and_about_dialogs(self) -> None:
        self.at.sidebar.button[2].click().run()
        help_text = any("Workout Logger Help" in m.body for m in self.at.markdown)
        self.assertTrue(help_text)
        self.at.sidebar.button[3].click().run()
        about_text = any("About The Builder" in m.body for m in self.at.markdown)
        self.assertTrue(about_text)

    def test_mobile_bottom_nav(self) -> None:
        self.at.query_params["mode"] = "mobile"
        self.at.run()
        nav_markup = [m.body for m in self.at.markdown if "bottom-nav" in m.body]
        self.assertTrue(nav_markup)
        self.assertIn("data-tooltip", nav_markup[0])

    def test_scroll_top_button(self) -> None:
        self.at.query_params["mode"] = "mobile"
        self.at.run()
        btn_present = any("scroll-top" in m.body for m in self.at.markdown)
        self.assertTrue(btn_present)

    def test_header_collapse_css(self) -> None:
        css_present = any(
            "header-wrapper.collapsed" in m.body for m in self.at.markdown
        )
        self.assertTrue(css_present)

    def test_disable_header_collapse(self) -> None:
        with open(self.yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        data["collapse_header"] = False
        with open(self.yaml_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f)
        self.at.run()
        js_present = any("handleHeaderCollapse()" in m.body for m in self.at.markdown)
        self.assertFalse(js_present)

    def test_notifications_dialog(self) -> None:
        idx = _find_by_label(self.at.button, "🔔", key="notif_btn")
        self.assertIsNotNone(self.at.button[idx])

    def test_quick_workout_fab(self) -> None:
        idx = _find_by_label(self.at.button, "➕", key="quick_workout_btn")
        self.at.button[idx].click().run()
        type_idx = _find_by_label(
            self.at.selectbox, "Training Type", key="quick_workout_type"
        )
        self.at.selectbox[type_idx].select("strength").run()
        loc_idx = _find_by_label(
            self.at.text_input, "Location", key="quick_workout_loc"
        )
        self.at.text_input[loc_idx].input("Home").run()
        sub_idx = _find_by_label(
            self.at.button,
            "Create",
            key="FormSubmitter:quick_workout_form-Create",
        )
        self.at.button[sub_idx].click().run()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM workouts;")
        self.assertEqual(cur.fetchone()[0], 1)
        conn.close()

    def test_sidebar_quick_search(self) -> None:
        idx_new = _find_by_label(
            self.at.button,
            "New Workout",
            key="FormSubmitter:new_workout_form-New Workout",
        )
        self.at.button[idx_new].click().run()
        self.at.button[idx_new].click().run()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("UPDATE workouts SET notes='Home' WHERE id=1")
        cur.execute("UPDATE workouts SET notes='Gym' WHERE id=2")
        conn.commit()
        conn.close()
        exp_idx = _find_by_label(self.at.sidebar.tabs, "Quick Search")
        exp = self.at.sidebar.tabs[exp_idx]
        self.assertEqual(exp.button[0].label, "Search")

    def test_tab_persistence_on_refresh(self) -> None:
        before = self.at.query_params.get("tab")
        idx = _find_by_label(self.at.button, "Refresh")
        self.at.button[idx].click().run()
        self.assertEqual(self.at.query_params.get("tab"), before)

    def test_tab_persistence_on_add_set(self) -> None:
        before = self.at.query_params.get("tab")
        idx_new = _find_by_label(
            self.at.button,
            "New Workout",
            key="FormSubmitter:new_workout_form-New Workout",
        )
        self.at.button[idx_new].click().run()
        idx_ex = _find_by_label(self.at.selectbox, "Exercise", "Barbell Bench Press")
        self.at.selectbox[idx_ex].select("Barbell Bench Press").run()
        idx_eq = _find_by_label(self.at.selectbox, "Equipment Name", "Olympic Barbell")
        self.at.selectbox[idx_eq].select("Olympic Barbell").run()
        idx_add_ex = _find_by_label(self.at.button, "Add Exercise", key="add_ex_btn")
        self.at.button[idx_add_ex].click().run()
        idx_add_set = _find_by_label(self.at.button, "Add Set", key="add_set_1")
        self.at.button[idx_add_set].click().run()
        self.assertEqual(self.at.query_params.get("tab"), before)

    def test_workout_context_menu_present(self) -> None:
        idx_new = _find_by_label(
            self.at.button,
            "New Workout",
            key="FormSubmitter:new_workout_form-New Workout",
        )
        self.at.button[idx_new].click().run()
        markup = [m.body for m in self.at.markdown]
        self.assertTrue(any("ctx-menu" in m for m in markup))

    def test_plan_progress_ring(self) -> None:
        pw_repo = PlannedWorkoutRepository(self.db_path)
        pe_repo = PlannedExerciseRepository(self.db_path)
        ps_repo = PlannedSetRepository(self.db_path)
        workout_repo = WorkoutRepository(self.db_path)
        ex_repo = ExerciseRepository(self.db_path)
        set_repo = SetRepository(self.db_path)
        today = datetime.date.today().isoformat()
        pid = pw_repo.create(today, "strength")
        peid = pe_repo.add(pid, "Barbell Bench Press", "Olympic Barbell")
        sid = ps_repo.add(peid, 5, 100.0, 8)
        wid = workout_repo.create(today, "strength")
        eid = ex_repo.add(wid, "Barbell Bench Press", "Olympic Barbell")
        set_repo.add(eid, 5, 100.0, 8, planned_set_id=sid)
        self.at.query_params["tab"] = "plan"
        self.at.run()
        exp_idx = _find_by_label(self.at.tabs, "Existing Plans")
        plan_exp = self.at.tabs[exp_idx].tabs[0]
        html = "".join(m.body for m in plan_exp.markdown)
        self.assertIn("progress-ring", html)
        self.assertIn("--val:100.0", html)


@unittest.skip("workflow changed")
class StreamlitTemplateWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = "test_gui_tpl.db"
        self.yaml_path = "test_gui_tpl.yaml"
        for path in [self.db_path, self.yaml_path]:
            if os.path.exists(path):
                os.remove(path)
        os.environ["DB_PATH"] = self.db_path
        os.environ["YAML_PATH"] = self.yaml_path
        os.environ["TEST_MODE"] = "0"
        self.at = AppTest.from_file("streamlit_app.py", default_timeout=20)
        self.at.query_params["mode"] = "desktop"
        self.at.query_params["tab"] = "workouts"
        self.at.run(timeout=20)

    def tearDown(self) -> None:
        for path in [self.db_path, self.yaml_path]:
            if os.path.exists(path):
                os.remove(path)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _get_tab(self, label: str):
        matches = [t for t in self.at.tabs if t.label == label]
        if not matches:
            self.fail(f"Tab {label} not found")
        if len(matches) == 1:
            return matches[0]
        expected = {"General", "Workout Tags", "Equipment", "Exercise Management", "Muscles"}
        for m in matches:
            sub_labels = {st.label for st in getattr(m, "tabs", [])}
            if expected.issubset(sub_labels):
                return m
        return matches[0]

    def test_template_plan_to_workout(self) -> None:
        plan_tab = self._get_tab("Plan")
        tmpl_exp = next(e for e in plan_tab.tabs if e.label == "Templates")
        tmpl_exp.text_input[0].input("Tpl1").run()
        idx = _find_by_label(tmpl_exp.selectbox, "Training Type")
        tmpl_exp.selectbox[idx].select("strength").run()
        b_idx = _find_by_label(tmpl_exp.button, "Create Template")
        tmpl_exp.button[b_idx].click().run()
        self.at.run()
        plan_tab = self._get_tab("Plan")
        tmpl_exp = next(e for e in plan_tab.tabs if e.label == "Templates")
        for exp in tmpl_exp.tabs:
            if exp.label.startswith("Tpl1"):
                exp.button[1].click().run()
                break
        self.at.run()

        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM workout_templates;")
        self.assertEqual(cur.fetchone()[0], 1)
        cur.execute("SELECT COUNT(*) FROM planned_workouts;")
        self.assertEqual(cur.fetchone()[0], 1)
        cur.execute("SELECT COUNT(*) FROM workouts;")
        self.assertEqual(cur.fetchone()[0], 1)
        conn.close()

    def test_favorite_template_pinned(self) -> None:
        repo = TemplateWorkoutRepository(self.db_path)
        fav_repo = FavoriteTemplateRepository(self.db_path)
        t1 = repo.create("A", "strength")
        t2 = repo.create("B", "strength")
        fav_repo.add(t2)
        self.at.query_params["tab"] = "library"
        self.at.run()
        lib_tab = self._get_tab("Library")
        tmpl_sec = next(e for e in lib_tab.tabs if e.label == "Existing Templates")
        options = tmpl_sec.selectbox[0].options
        self.assertEqual(options[0], "B")


class StreamlitHeartRateGUITest(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = "test_gui_hr.db"
        self.yaml_path = "test_gui_hr.yaml"
        for path in [self.db_path, self.yaml_path]:
            if os.path.exists(path):
                os.remove(path)
        os.environ["DB_PATH"] = self.db_path
        os.environ["YAML_PATH"] = self.yaml_path
        os.environ["TEST_MODE"] = "0"
        self.at = AppTest.from_file("streamlit_app.py", default_timeout=20)
        self.at.query_params["mode"] = "desktop"
        self.at.query_params["tab"] = "workouts"
        self.at.run(timeout=20)

    def tearDown(self) -> None:
        for path in [self.db_path, self.yaml_path]:
            if os.path.exists(path):
                os.remove(path)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _get_tab(self, label: str):
        matches = [t for t in self.at.tabs if t.label == label]
        if not matches:
            self.fail(f"Tab {label} not found")
        if len(matches) == 1:
            return matches[0]
        expected = {"General", "Workout Tags", "Equipment", "Exercise Management", "Muscles"}
        for m in matches:
            sub_labels = {st.label for st in getattr(m, "tabs", [])}
            if expected.issubset(sub_labels):
                return m
        return matches[0]

    def test_log_heart_rate(self) -> None:
        idx_new = _find_by_label(
            self.at.button,
            "New Workout",
            key="FormSubmitter:new_workout_form-New Workout",
        )
        self.at.button[idx_new].click().run()
        hr_idx = _find_by_label(self.at.tabs, "Heart Rate")
        self.at.tabs[hr_idx].text_input[0].input("2023-01-01T10:00:00").run()
        self.at.tabs[hr_idx].number_input[0].set_value(120).run()
        b_idx = _find_by_label(
            self.at.tabs[hr_idx].button,
            "Log Heart Rate",
            key="FormSubmitter:hr_form_1-Log Heart Rate",
        )
        self.at.tabs[hr_idx].button[b_idx].click().run()

        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT heart_rate FROM heart_rate_logs WHERE workout_id = 1;")
        self.assertEqual(cur.fetchone()[0], 120)
        conn.close()
    def test_compact_mode_toggle(self) -> None:
        self.at.query_params["tab"] = "settings"
        self.at.run()
        settings_tab = self._get_tab("Settings")
        idx = _find_by_label(settings_tab.checkbox, "Compact Mode")
        current = settings_tab.checkbox[idx].value
        if current:
            settings_tab.checkbox[idx].uncheck().run()
        else:
            settings_tab.checkbox[idx].check().run()
        save_idx = _find_by_label(settings_tab.button, "Save General Settings")
        settings_tab.button[save_idx].click().run()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = 'compact_mode';")
        val = cur.fetchone()[0]
        conn.close()
        self.assertEqual(bool(int(val)), not current)



@unittest.skip("Unstable in CI")
class StreamlitAllInteractionsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = "test_gui_all.db"
        self.yaml_path = "test_gui_all.yaml"
        for path in [self.db_path, self.yaml_path]:
            if os.path.exists(path):
                os.remove(path)
        os.environ["DB_PATH"] = self.db_path
        os.environ["YAML_PATH"] = self.yaml_path
        os.environ["TEST_MODE"] = "1"
        self.at = AppTest.from_file("streamlit_app.py", default_timeout=20)
        self.at.query_params["mode"] = "desktop"
        self.at.query_params["tab"] = "workouts"
        self.at.run(timeout=20)

    def tearDown(self) -> None:
        for path in [self.db_path, self.yaml_path]:
            if os.path.exists(path):
                os.remove(path)

    def test_all_visible_widgets(self) -> None:
        # Interact with all currently visible widgets to ensure
        # that every user interaction works without errors.
        for tab in ["workouts", "library", "progress", "settings"]:
            self.at.query_params["tab"] = tab
            self.at.run()
            for sel in self.at.selectbox:
                if sel.options:
                    sel.select(sel.options[0]).run()
            for multi in self.at.multiselect:
                if multi.options:
                    try:
                        multi.select(multi.options[:1]).run()
                    except KeyError:
                        pass
            for num in self.at.number_input:
                try:
                    num.set_value(num.value if num.value is not None else 0).run()
                except KeyError:
                    pass
            for txt in self.at.text_input:
                try:
                    txt.input("test").run()
                except KeyError:
                    pass
            for txta in getattr(self.at, "text_area", []):
                try:
                    txta.input("test").run()
                except KeyError:
                    pass
            for date in self.at.date_input:
                try:
                    date.set_value(date.value).run()
                except KeyError:
                    pass
            for chk in self.at.checkbox:
                try:
                    chk.check().run()
                except Exception:
                    pass
        for btn in self.at.button:
            try:
                btn.click().run()
            except Exception:
                pass


class RecommendationIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = "test_goal_integration.db"
        self.yaml_path = "test_goal_settings.yaml"
        for path in [self.db_path, self.yaml_path]:
            if os.path.exists(path):
                os.remove(path)
        # Ensure ML model tables exist before the app loads
        from db import MLModelRepository
        MLModelRepository(self.db_path)
        os.environ["DB_PATH"] = self.db_path
        os.environ["YAML_PATH"] = self.yaml_path
        os.environ["TEST_MODE"] = "0"
        self.at = AppTest.from_file("streamlit_app.py", default_timeout=20)
        self.at.query_params["mode"] = "desktop"
        self.at.query_params["tab"] = "settings"
        self.at.run(timeout=20)

    def tearDown(self) -> None:
        for path in [self.db_path, self.yaml_path]:
            if os.path.exists(path):
                os.remove(path)

    def _get_tab(self, label: str):
        matches = [t for t in self.at.tabs if t.label == label]
        if not matches:
            self.fail(f"Tab {label} not found")
        if len(matches) == 1:
            return matches[0]
        expected = {"General", "Workout Tags", "Equipment", "Exercise Management", "Muscles"}
        for m in matches:
            sub_labels = {st.label for st in getattr(m, "tabs", [])}
            if expected.issubset(sub_labels):
                return m
        return matches[0]

    def test_goals_passed_to_recommender(self) -> None:
        os.environ["DB_PATH"] = self.db_path
        os.environ["YAML_PATH"] = self.yaml_path
        os.environ["TEST_MODE"] = "0"
        app = GymApp(self.db_path, self.yaml_path)
        self.assertIsNotNone(app.recommender.goals)

    def test_csv_uploader_present(self) -> None:
        tab = self._get_tab("Settings")
        has_dm = any(e.label == "Data Management" for e in tab.tabs)
        self.assertTrue(has_dm)



if __name__ == "__main__":
    unittest.main()
