import os
import sqlite3
from streamlit.testing.v1 import AppTest

def test_streamlit_workflow(tmp_path):
    db_path = tmp_path / "test.db"
    yaml_path = tmp_path / "settings.yaml"
    os.environ["DB_PATH"] = str(db_path)
    os.environ["YAML_PATH"] = str(yaml_path)
    os.environ["TEST_MODE"] = "1"

    at = AppTest.from_file("streamlit_app.py", default_timeout=20)
    at.query_params["mode"] = "desktop"
    at.query_params["tab"] = "workouts"
    at.run(timeout=20)

    at.button[1].click().run()
    at.selectbox[3].select("Barbell Bench Press").run()
    at.selectbox[5].select("Olympic Barbell").run()
    at.button[9].click().run()
    at.number_input[0].set_value(5).run()
    at.number_input[1].set_value(100.0).run()
    at.button[13].click().run()

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM workouts;")
    assert cur.fetchone()[0] == 1
    cur.execute("SELECT name FROM exercises;")
    assert cur.fetchone()[0] == "Barbell Bench Press"
    cur.execute("SELECT reps, weight FROM sets;")
    assert cur.fetchone() == (5, 100.0)
    conn.close()
