import sqlite3
import sys

def migrate(db_path='workout.db'):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(exercise_images);")
    cols = [r[1] for r in cur.fetchall()]
    if 'thumbnail_path' not in cols:
        cur.execute("ALTER TABLE exercise_images ADD COLUMN thumbnail_path TEXT;")
    cur.execute("PRAGMA table_info(planned_workouts);")
    cols = [r[1] for r in cur.fetchall()]
    if 'position' not in cols:
        cur.execute("ALTER TABLE planned_workouts ADD COLUMN position INTEGER NOT NULL DEFAULT 0;")
    conn.commit()
    conn.close()

if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else 'workout.db'
    migrate(path)
