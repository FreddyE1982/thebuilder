import os
import sqlite3
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from db import Database


class TestSchemaMigration:
    def test_drops_existing_backup_table(self, tmp_path):
        db_file = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_file))
        conn.execute(
            "CREATE TABLE sets (id INTEGER PRIMARY KEY AUTOINCREMENT, exercise_id INTEGER, reps INTEGER, weight REAL, rpe INTEGER)"
        )
        conn.execute("CREATE TABLE sets_old (id INTEGER)")
        conn.commit()
        conn.close()

        Database(str(db_file))

        conn = sqlite3.connect(str(db_file))
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sets_old'"
        )
        assert cur.fetchone() is None
        cur = conn.execute("PRAGMA table_info(sets)")
        cols = [row[1] for row in cur.fetchall()]
        assert "diff_reps" in cols
        conn.close()
