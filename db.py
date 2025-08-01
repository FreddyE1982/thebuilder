import sqlite3
import aiosqlite
import csv
import os
import io
import datetime
import json
import difflib
from contextlib import contextmanager, asynccontextmanager
from typing import List, Tuple, Optional, Iterable, Set

from config import YamlConfig
from settings_schema import validate_settings


class Database:
    """Provides SQLite connection management and schema initialization."""

    _TABLE_DEFINITIONS = {
        "workouts": (
            """CREATE TABLE workouts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    name TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    timezone TEXT NOT NULL DEFAULT 'UTC',
                    training_type TEXT NOT NULL DEFAULT 'strength',
                    notes TEXT,
                    location TEXT,
                    icon TEXT,
                    rating INTEGER,
                    mood_before INTEGER,
                    mood_after INTEGER
                );""",
            [
                "id",
                "date",
                "name",
                "start_time",
                "end_time",
                "timezone",
                "training_type",
                "notes",
                "location",
                "icon",
                "rating",
                "mood_before",
                "mood_after",
            ],
        ),
        "equipment": (
            """CREATE TABLE equipment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    equipment_type TEXT NOT NULL,
                    name TEXT NOT NULL UNIQUE,
                    muscles TEXT NOT NULL,
                    is_custom INTEGER NOT NULL DEFAULT 0
                );""",
            ["id", "equipment_type", "name", "muscles", "is_custom"],
        ),
        "equipment_types": (
            """CREATE TABLE equipment_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    is_custom INTEGER NOT NULL DEFAULT 0
                );""",
            ["id", "name", "is_custom"],
        ),
        "muscles": (
            """CREATE TABLE muscles (
                    name TEXT PRIMARY KEY,
                    canonical_name TEXT NOT NULL
                );""",
            ["name", "canonical_name"],
        ),
        "muscle_groups": (
            """CREATE TABLE muscle_groups (
                    name TEXT PRIMARY KEY
                );""",
            ["name"],
        ),
        "muscle_group_members": (
            """CREATE TABLE muscle_group_members (
                    muscle_name TEXT PRIMARY KEY,
                    group_name TEXT NOT NULL,
                    FOREIGN KEY(muscle_name) REFERENCES muscles(name) ON DELETE CASCADE,
                    FOREIGN KEY(group_name) REFERENCES muscle_groups(name) ON DELETE CASCADE
                );""",
            ["muscle_name", "group_name"],
        ),
        "exercise_names": (
            """CREATE TABLE exercise_names (
                    name TEXT PRIMARY KEY,
                    canonical_name TEXT NOT NULL
                );""",
            ["name", "canonical_name"],
        ),
        "exercise_catalog": (
            """CREATE TABLE exercise_catalog (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    muscle_group TEXT NOT NULL,
                    name TEXT NOT NULL UNIQUE,
                    variants TEXT,
                    equipment_names TEXT,
                    primary_muscle TEXT,
                    secondary_muscle TEXT,
                    tertiary_muscle TEXT,
                    other_muscles TEXT,
                    video_url TEXT,
                    is_custom INTEGER NOT NULL DEFAULT 0
                );""",
            [
                "id",
                "muscle_group",
                "name",
                "variants",
                "equipment_names",
                "primary_muscle",
                "secondary_muscle",
                "tertiary_muscle",
                "other_muscles",
                "video_url",
                "is_custom",
            ],
        ),
        "exercise_variants": (
            """CREATE TABLE exercise_variants (
                    exercise_name TEXT NOT NULL,
                    variant_name TEXT NOT NULL,
                    PRIMARY KEY (exercise_name, variant_name),
                    FOREIGN KEY(exercise_name) REFERENCES exercise_catalog(name) ON DELETE CASCADE,
                    FOREIGN KEY(variant_name) REFERENCES exercise_catalog(name) ON DELETE CASCADE
                );""",
            ["exercise_name", "variant_name"],
        ),
        "exercise_images": (
            """CREATE TABLE exercise_images (
                    exercise_name TEXT PRIMARY KEY,
                    path TEXT NOT NULL,
                    thumbnail_path TEXT,
                    FOREIGN KEY(exercise_name) REFERENCES exercise_catalog(name) ON DELETE CASCADE
                );""",
            ["exercise_name", "path", "thumbnail_path"],
        ),
        "exercises": (
            """CREATE TABLE exercises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workout_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    equipment_name TEXT,
                    note TEXT,
                    FOREIGN KEY(workout_id) REFERENCES workouts(id) ON DELETE CASCADE,
                    FOREIGN KEY(equipment_name) REFERENCES equipment(name)
                );""",
            ["id", "workout_id", "name", "equipment_name", "note"],
        ),
        "planned_workouts": (
            """CREATE TABLE planned_workouts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    training_type TEXT NOT NULL DEFAULT 'strength',
                    position INTEGER NOT NULL DEFAULT 0
                );""",
            ["id", "date", "training_type", "position"],
        ),
        "planned_exercises": (
            """CREATE TABLE planned_exercises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    planned_workout_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    equipment_name TEXT,
                    FOREIGN KEY(planned_workout_id) REFERENCES planned_workouts(id) ON DELETE CASCADE,
                    FOREIGN KEY(equipment_name) REFERENCES equipment(name)
                );""",
            ["id", "planned_workout_id", "name", "equipment_name"],
        ),
        "planned_sets": (
            """CREATE TABLE planned_sets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    planned_exercise_id INTEGER NOT NULL,
                    reps INTEGER NOT NULL,
                    weight REAL NOT NULL,
                    rpe INTEGER NOT NULL,
                    FOREIGN KEY(planned_exercise_id) REFERENCES planned_exercises(id) ON DELETE CASCADE
                );""",
            ["id", "planned_exercise_id", "reps", "weight", "rpe"],
        ),
        "workout_templates": (
            """CREATE TABLE workout_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    training_type TEXT NOT NULL DEFAULT 'strength',
                    position INTEGER NOT NULL DEFAULT 0,
                    color TEXT DEFAULT '#ffffff',
                    last_used TEXT
                );""",
            ["id", "name", "training_type", "position", "color", "last_used"],
        ),
        "template_exercises": (
            """CREATE TABLE template_exercises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    equipment_name TEXT,
                    FOREIGN KEY(template_id) REFERENCES workout_templates(id) ON DELETE CASCADE,
                    FOREIGN KEY(equipment_name) REFERENCES equipment(name)
                );""",
            ["id", "template_id", "name", "equipment_name"],
        ),
        "template_sets": (
            """CREATE TABLE template_sets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_exercise_id INTEGER NOT NULL,
                    reps INTEGER NOT NULL,
                    weight REAL NOT NULL,
                    rpe INTEGER NOT NULL,
                    FOREIGN KEY(template_exercise_id) REFERENCES template_exercises(id) ON DELETE CASCADE
                );""",
            ["id", "template_exercise_id", "reps", "weight", "rpe"],
        ),
        "sets": (
            """CREATE TABLE sets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exercise_id INTEGER NOT NULL,
                    reps INTEGER NOT NULL,
                    weight REAL NOT NULL,
                    rpe INTEGER NOT NULL,
                    position INTEGER NOT NULL,
                    planned_set_id INTEGER,
                    diff_reps INTEGER NOT NULL DEFAULT 0,
                    diff_weight REAL NOT NULL DEFAULT 0,
                    diff_rpe INTEGER NOT NULL DEFAULT 0,
                    start_time TEXT,
                    end_time TEXT,
                    note TEXT,
                    rest_note TEXT,
                    warmup INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(exercise_id) REFERENCES exercises(id) ON DELETE CASCADE,
                    FOREIGN KEY(planned_set_id) REFERENCES planned_sets(id) ON DELETE SET NULL
                );""",
            [
                "id",
                "exercise_id",
                "reps",
                "weight",
                "rpe",
                "position",
                "planned_set_id",
                "diff_reps",
                "diff_weight",
                "diff_rpe",
                "start_time",
                "end_time",
                "note",
                "rest_note",
                "warmup",
            ],
        ),
        "settings": (
            """CREATE TABLE settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );""",
            ["key", "value"],
        ),
        "pyramid_tests": (
            """CREATE TABLE pyramid_tests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exercise_name TEXT NOT NULL DEFAULT 'Unknown',
                    date TEXT NOT NULL,
                    equipment_name TEXT,
                    starting_weight REAL,
                    failed_weight REAL,
                    max_achieved REAL,
                    test_duration_minutes INTEGER,
                    rest_between_attempts TEXT,
                    rpe_per_attempt TEXT,
                    time_of_day TEXT,
                    sleep_hours REAL,
                    stress_level INTEGER,
                    nutrition_quality INTEGER
                );""",
            [
                "id",
                "exercise_name",
                "date",
                "equipment_name",
                "starting_weight",
                "failed_weight",
                "max_achieved",
                "test_duration_minutes",
                "rest_between_attempts",
                "rpe_per_attempt",
                "time_of_day",
                "sleep_hours",
                "stress_level",
                "nutrition_quality",
            ],
        ),
        "pyramid_entries": (
            """CREATE TABLE pyramid_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pyramid_test_id INTEGER NOT NULL,
                    weight REAL NOT NULL,
                    FOREIGN KEY(pyramid_test_id) REFERENCES pyramid_tests(id) ON DELETE CASCADE
                );""",
            ["id", "pyramid_test_id", "weight"],
        ),
        "gamification_points": (
            """CREATE TABLE gamification_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workout_id INTEGER NOT NULL,
                    points REAL NOT NULL,
                    FOREIGN KEY(workout_id) REFERENCES workouts(id) ON DELETE CASCADE
                );""",
            ["id", "workout_id", "points"],
        ),
        "challenges": (
            """CREATE TABLE challenges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    target INTEGER NOT NULL,
                    progress INTEGER NOT NULL DEFAULT 0,
                    completed INTEGER NOT NULL DEFAULT 0
                );""",
            ["id", "name", "target", "progress", "completed"],
        ),
        "ml_models": (
            """CREATE TABLE ml_models (
                    name TEXT PRIMARY KEY,
                    state BLOB NOT NULL
                );""",
            ["name", "state"],
        ),
        "ml_logs": (
            """CREATE TABLE ml_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    prediction REAL NOT NULL,
                    confidence REAL NOT NULL
                );""",
            ["id", "name", "timestamp", "prediction", "confidence"],
        ),
        "ml_training_raw": (
            """CREATE TABLE ml_training_raw (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_name TEXT NOT NULL,
                    inputs TEXT NOT NULL,
                    target REAL NOT NULL
                );""",
            ["id", "model_name", "inputs", "target"],
        ),
        "body_weight_logs": (
            """CREATE TABLE body_weight_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    weight REAL NOT NULL
                );""",
            ["id", "date", "weight"],
        ),
        "wellness_logs": (
            """CREATE TABLE wellness_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    calories REAL,
                    sleep_hours REAL,
                    sleep_quality REAL,
                    stress_level INTEGER
                );""",
            [
                "id",
                "date",
                "calories",
                "sleep_hours",
                "sleep_quality",
                "stress_level",
            ],
        ),
        "heart_rate_logs": (
            """CREATE TABLE heart_rate_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workout_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    heart_rate INTEGER NOT NULL,
                    FOREIGN KEY(workout_id) REFERENCES workouts(id) ON DELETE CASCADE
                );""",
            ["id", "workout_id", "timestamp", "heart_rate"],
        ),
        "step_count_logs": (
            """CREATE TABLE step_count_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workout_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    steps INTEGER NOT NULL,
                    FOREIGN KEY(workout_id) REFERENCES workouts(id) ON DELETE CASCADE
                );""",
            ["id", "workout_id", "timestamp", "steps"],
        ),
        "favorite_exercises": (
            """CREATE TABLE favorite_exercises (
                    name TEXT PRIMARY KEY
                );""",
            ["name"],
        ),
        "favorite_templates": (
            """CREATE TABLE favorite_templates (
                    template_id INTEGER PRIMARY KEY,
                    FOREIGN KEY(template_id) REFERENCES workout_templates(id) ON DELETE CASCADE
                );""",
            ["template_id"],
        ),
        "favorite_workouts": (
            """CREATE TABLE favorite_workouts (
                    workout_id INTEGER PRIMARY KEY,
                    FOREIGN KEY(workout_id) REFERENCES workouts(id) ON DELETE CASCADE
                );""",
            ["workout_id"],
        ),
        "default_equipment": (
            """CREATE TABLE default_equipment (
                    exercise_name TEXT PRIMARY KEY,
                    equipment_name TEXT NOT NULL,
                    FOREIGN KEY(exercise_name) REFERENCES exercise_catalog(name) ON DELETE CASCADE,
                    FOREIGN KEY(equipment_name) REFERENCES equipment(name) ON DELETE CASCADE
                );""",
            ["exercise_name", "equipment_name"],
        ),
        "workout_reactions": (
            """CREATE TABLE workout_reactions (
                    workout_id INTEGER NOT NULL,
                    emoji TEXT NOT NULL,
                    count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(workout_id, emoji),
                    FOREIGN KEY(workout_id) REFERENCES workouts(id) ON DELETE CASCADE
                );""",
            ["workout_id", "emoji", "count"],
        ),
        "tags": (
            """CREATE TABLE tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                );""",
            ["id", "name"],
        ),
        "workout_tags": (
            """CREATE TABLE workout_tags (
                    workout_id INTEGER NOT NULL,
                    tag_id INTEGER NOT NULL,
                    PRIMARY KEY (workout_id, tag_id),
                    FOREIGN KEY(workout_id) REFERENCES workouts(id) ON DELETE CASCADE,
                    FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE
                );""",
            ["workout_id", "tag_id"],
        ),
        "exercise_tags": (
            """CREATE TABLE exercise_tags (
                    exercise_name TEXT NOT NULL,
                    tag_id INTEGER NOT NULL,
                    PRIMARY KEY (exercise_name, tag_id),
                    FOREIGN KEY(exercise_name) REFERENCES exercise_catalog(name) ON DELETE CASCADE,
                    FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE
                );""",
            ["exercise_name", "tag_id"],
        ),
        "goals": (
            """CREATE TABLE goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exercise_name TEXT NOT NULL,
                    name TEXT NOT NULL,
                    target_value REAL NOT NULL,
                    unit TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    target_date TEXT NOT NULL,
                    achieved INTEGER NOT NULL DEFAULT 0
                );""",
            [
                "id",
                "exercise_name",
                "name",
                "target_value",
                "unit",
                "start_date",
                "target_date",
                "achieved",
            ],
        ),
        "autoplanner_logs": (
            """CREATE TABLE autoplanner_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT
                );""",
            ["id", "timestamp", "status", "message"],
        ),
        "exercise_prescription_logs": (
            """CREATE TABLE exercise_prescription_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT
                );""",
            ["id", "timestamp", "status", "message"],
        ),
        "email_logs": (
            """CREATE TABLE email_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    address TEXT NOT NULL,
                    report_range TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    success INTEGER NOT NULL
                );""",
            [
                "id",
                "timestamp",
                "address",
                "report_range",
                "summary",
                "success",
            ],
        ),
        "ml_model_status": (
            """CREATE TABLE ml_model_status (
                    name TEXT PRIMARY KEY,
                    last_loaded TEXT,
                    last_train TEXT,
                    last_predict TEXT
                );""",
            ["name", "last_loaded", "last_train", "last_predict"],
        ),
        "notifications": (
            """CREATE TABLE notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    message TEXT NOT NULL,
                    read INTEGER NOT NULL DEFAULT 0
                );""",
            ["id", "timestamp", "message", "read"],
        ),
        "workout_comments": (
            """CREATE TABLE workout_comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workout_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    comment TEXT NOT NULL,
                    FOREIGN KEY(workout_id) REFERENCES workouts(id) ON DELETE CASCADE
                );""",
            ["id", "workout_id", "timestamp", "comment"],
        ),
        "api_keys": (
            """CREATE TABLE api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    api_key TEXT NOT NULL
                );""",
            ["id", "name", "api_key"],
        ),
        "weight_stats_cache": (
            """CREATE TABLE weight_stats_cache (
                    start_date TEXT,
                    end_date TEXT,
                    unit TEXT NOT NULL,
                    avg REAL NOT NULL,
                    min REAL NOT NULL,
                    max REAL NOT NULL,
                    PRIMARY KEY (start_date, end_date, unit)
                );""",
            ["start_date", "end_date", "unit", "avg", "min", "max"],
        ),
    }

    def __init__(self, db_path: str = "workout.db", db_url: str | None = None) -> None:
        self._db_url = db_url or os.environ.get("DB_URL")
        self._db_path = db_path
        self._ensure_schema()
        self._import_equipment_data()
        self._import_exercise_catalog_data()
        self._sync_muscles()
        self._sync_exercise_names()
        self._init_settings()
        self._ensure_views()
        self.vacuum()

    @contextmanager
    def _connection(self):
        if self._db_url and self._db_url.startswith("postgresql"):
            import psycopg2
            connection = psycopg2.connect(self._db_url)
        else:
            connection = sqlite3.connect(self._db_path)
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _ensure_schema(self) -> None:
        with self._connection() as conn:
            cursor = conn.cursor()
            if not (self._db_url and self._db_url.startswith("postgresql")):
                cursor.execute("PRAGMA foreign_keys=off;")
            for table, (sql, columns) in self._TABLE_DEFINITIONS.items():
                self._ensure_table(conn, table, sql, columns)
            if not (self._db_url and self._db_url.startswith("postgresql")):
                cursor.execute("PRAGMA foreign_keys=on;")

    def _ensure_views(self) -> None:
        """Create required SQLite views for caching."""
        with self._connection() as conn:
            conn.execute(
                "CREATE VIEW IF NOT EXISTS v_weight_stats AS "
                "SELECT start_date, end_date, unit, avg, min, max "
                "FROM weight_stats_cache;"
            )

    def _ensure_table(
        self, conn: sqlite3.Connection, table: str, sql: str, columns: List[str]
    ) -> None:
        if self._db_url and self._db_url.startswith("postgresql"):
            import re
            sql_pg = re.sub(
                r"INTEGER PRIMARY KEY AUTOINCREMENT",
                "SERIAL PRIMARY KEY",
                sql,
            )
            sql_pg = sql_pg.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS")
            try:
                conn.execute(sql_pg)
            except Exception:
                pass
            return

        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table,)
        )
        if cur.fetchone() is None:
            conn.execute(sql)
            return

        cur = conn.execute(f"PRAGMA table_info({table});")
        existing_cols = [row[1] for row in cur.fetchall()]
        if existing_cols == columns:
            return

        conn.execute(f"ALTER TABLE {table} RENAME TO {table}_old;")
        conn.execute(sql)

        common = [c for c in existing_cols if c in columns]
        if common:
            cols = ", ".join(common)
            missing = [c for c in columns if c not in existing_cols]
            if missing:
                def default_val(col: str) -> str:
                    if col == "training_type":
                        return "'strength'"
                    if col == "position":
                        return "0"
                    if col == "timezone":
                        return "'UTC'"
                    if col in ("diff_reps", "diff_weight", "diff_rpe", "warmup"):
                        return "0"
                    if col == "icon":
                        return "''"
                    return "NULL"

                defaults = ", ".join(default_val(c) for c in missing)
                conn.execute(
                    f"INSERT INTO {table} ({cols}, {', '.join(missing)}) SELECT {cols}, {defaults} FROM {table}_old;"
                )
            else:
                conn.execute(
                    f"INSERT INTO {table} ({cols}) SELECT {cols} FROM {table}_old;"
                )
        conn.execute(f"DROP TABLE {table}_old;")

    def _import_equipment_data(self) -> None:
        csv_path = os.path.join(
            os.path.dirname(__file__), "table3_equipment_muscles.csv"
        )
        if not os.path.exists(csv_path):
            return
        with open(csv_path, newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            records = [
                (
                    row["Equipment Type Group"],
                    row["Equipment Name"],
                    row["Muscles Trained"],
                )
                for row in reader
            ]
        with self._connection() as conn:
            for equipment_type, name, muscles in records:
                conn.execute(
                    "INSERT OR IGNORE INTO equipment_types (name, is_custom) VALUES (?, 0);",
                    (equipment_type,),
                )
                conn.execute(
                    "INSERT INTO equipment (equipment_type, name, muscles, is_custom) VALUES (?, ?, ?, 0) "
                    "ON CONFLICT(name) DO UPDATE SET equipment_type=excluded.equipment_type, muscles=excluded.muscles;",
                    (equipment_type, name, muscles),
                )

    def _import_exercise_catalog_data(self) -> None:
        csv_path = os.path.join(
            os.path.dirname(__file__), "table1_exercise_database.csv"
        )
        if not os.path.exists(csv_path):
            return
        with open(csv_path, newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            records = [
                (
                    row["Muscle Group"],
                    row["Exercise Name"],
                    row["Variants"],
                    row["Equipment Name(s)"],
                    row["Primary Muscle Trained"],
                    row.get("Secondary Muscle Trained", ""),
                    row.get("Tertiary Muscle Trained", ""),
                    row.get("Other Muscles Trained", ""),
                )
                for row in reader
            ]
        with self._connection() as conn:
            for (
                muscle_group,
                name,
                variants,
                equipment_names,
                primary_muscle,
                secondary_muscle,
                tertiary_muscle,
                other_muscles,
            ) in records:
                conn.execute(
                    "INSERT INTO exercise_catalog (muscle_group, name, variants, equipment_names, primary_muscle, secondary_muscle, tertiary_muscle, other_muscles, is_custom) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0) "
                    "ON CONFLICT(name) DO UPDATE SET muscle_group=excluded.muscle_group, variants=excluded.variants, equipment_names=excluded.equipment_names, primary_muscle=excluded.primary_muscle, secondary_muscle=excluded.secondary_muscle, tertiary_muscle=excluded.tertiary_muscle, other_muscles=excluded.other_muscles;",
                    (
                        muscle_group,
                        name,
                        variants,
                        equipment_names,
                        primary_muscle,
                        secondary_muscle,
                        tertiary_muscle,
                        other_muscles,
                    ),
                )

    def _sync_muscles(self) -> None:
        with self._connection() as conn:
            names: Set[str] = set()
            rows = conn.execute("SELECT muscles FROM equipment;").fetchall()
            for row in rows:
                for m in row[0].split("|"):
                    if m:
                        names.add(m)
            rows = conn.execute(
                "SELECT primary_muscle, secondary_muscle, tertiary_muscle, other_muscles FROM exercise_catalog;"
            ).fetchall()
            for pm, sm, tm, om in rows:
                for field in [pm, sm, tm, om]:
                    if field:
                        for m in field.split("|"):
                            if m:
                                names.add(m)
            for n in names:
                conn.execute(
                    "INSERT OR IGNORE INTO muscles (name, canonical_name) VALUES (?, ?);",
                    (n, n),
                )

    def _sync_exercise_names(self) -> None:
        with self._connection() as conn:
            names: Set[str] = set()
            rows = conn.execute("SELECT name FROM exercise_catalog;").fetchall()
            for row in rows:
                if row[0]:
                    names.add(row[0])
            rows = conn.execute("SELECT name FROM exercises;").fetchall()
            for row in rows:
                if row[0]:
                    names.add(row[0])
            rows = conn.execute("SELECT name FROM planned_exercises;").fetchall()
            for row in rows:
                if row[0]:
                    names.add(row[0])
            for n in names:
                conn.execute(
                    "INSERT OR IGNORE INTO exercise_names (name, canonical_name) VALUES (?, ?);",
                    (n, n),
                )

    def _init_settings(self) -> None:
        defaults = {
            "body_weight": "80.0",
            "height": "1.75",
            "months_active": "1",
            "theme": "light",
            "color_theme": "red",
            "accent_color": "#ff4b4b",
            "auto_dark_mode": "0",
            "game_enabled": "0",
            "ml_all_enabled": "1",
            "ml_training_enabled": "1",
            "ml_prediction_enabled": "1",
            "ml_rpe_training_enabled": "1",
            "ml_rpe_prediction_enabled": "1",
            "ml_volume_training_enabled": "1",
            "ml_volume_prediction_enabled": "1",
            "ml_readiness_training_enabled": "1",
            "ml_readiness_prediction_enabled": "1",
            "ml_progress_training_enabled": "1",
            "ml_progress_prediction_enabled": "1",
            "ml_goal_training_enabled": "1",
            "ml_goal_prediction_enabled": "1",
            "ml_injury_training_enabled": "1",
            "ml_injury_prediction_enabled": "1",
            "experimental_models_enabled": "0",
            "compact_mode": "0",
            "email_weekly_enabled": "0",
            "weekly_report_email": "",
            "weight_unit": "kg",
            "time_format": "24h",
            "quick_weights": "20,40,60,80,100",
            "quick_weight_increment": "0.5",
            "bookmarked_views": "",
            "pinned_stats": "",
            "hide_completed_plans": "0",
            "hide_completed_sets": "0",
            "hide_nav_labels": "0",
            "simple_mode": "0",
            "hide_advanced_charts": "0",
            "vertical_nav": "0",
            "daily_reminders_enabled": "0",
            "app_version": "1.0.0",
            "rpe_scale": "10",
            "language": "en",
            "show_help_tips": "0",
        }
        with self._connection() as conn:
            for key, value in defaults.items():
                conn.execute(
                    "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?);",
                    (key, value),
                )

    def vacuum(self) -> None:
        """Run SQLite VACUUM to reduce database size."""
        with self._connection() as conn:
            conn.execute("VACUUM;")


class BaseRepository(Database):
    """Base repository providing helper methods."""

    def execute(self, query: str, params: Tuple = ()) -> int:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.lastrowid

    def fetch_all(self, query: str, params: Tuple = ()) -> List[Tuple]:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()

    def _delete_all(self, table: str) -> None:
        self.execute(f"DELETE FROM {table};")


class AsyncDatabase(Database):
    """Provides asynchronous connection management."""

    @asynccontextmanager
    async def _async_connection(self):
        if self._db_url and self._db_url.startswith("postgresql"):
            import asyncpg
            conn = await asyncpg.connect(self._db_url)
            try:
                yield conn
            finally:
                await conn.close()
        else:
            conn = await aiosqlite.connect(self._db_path)
            try:
                yield conn
                await conn.commit()
            finally:
                await conn.close()


class AsyncBaseRepository(AsyncDatabase):
    """Asynchronous variant of BaseRepository using aiosqlite."""

    async def execute(self, query: str, params: Tuple = ()) -> int:
        async with self._async_connection() as conn:
            if self._db_url and self._db_url.startswith("postgresql"):
                await conn.execute(query, *params)
                rowid = await conn.fetchval("SELECT LASTVAL();")
                return int(rowid) if rowid is not None else 0
            else:
                cursor = await conn.execute(query, params)
                await conn.commit()
                return cursor.lastrowid

    async def fetch_all(self, query: str, params: Tuple = ()) -> List[Tuple]:
        async with self._async_connection() as conn:
            if self._db_url and self._db_url.startswith("postgresql"):
                rows = await conn.fetch(query, *params)
                return [tuple(r) for r in rows]
            else:
                cursor = await conn.execute(query, params)
                rows = await cursor.fetchall()
                return rows

    async def _delete_all(self, table: str) -> None:
        await self.execute(f"DELETE FROM {table};")


class AsyncWorkoutRepository(AsyncBaseRepository):
    """Async repository for workout table operations."""

    async def create(
        self,
        date: str,
        timezone: str = "UTC",
        training_type: str = "strength",
        notes: str | None = None,
        location: str | None = None,
        rating: Optional[int] = None,
        mood_before: Optional[int] = None,
        mood_after: Optional[int] = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> int:
        return await self.execute(
            "INSERT INTO workouts (date, timezone, training_type, notes, location, rating, mood_before, mood_after, start_time, end_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
            (
                date,
                timezone,
                training_type,
                notes,
                location,
                rating,
                mood_before,
                mood_after,
                start_time,
                end_time,
            ),
        )

    async def fetch_all_workouts(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        sort_by: str = "id",
        descending: bool = True,
        limit: int | None = None,
        offset: int | None = None,
    ) -> List[
        Tuple[
            int,
            str,
            Optional[str],
            Optional[str],
            Optional[str],
            str,
            str,
            Optional[str],
            Optional[int],
            Optional[int],
            Optional[int],
        ]
    ]:
        query = (
            "SELECT id, date, start_time, end_time, timezone, training_type, notes, location, rating, mood_before, mood_after FROM workouts"
        )
        params: list[str | int] = []
        where_clauses: list[str] = []
        if start_date:
            where_clauses.append("date >= ?")
            params.append(start_date)
        if end_date:
            where_clauses.append("date <= ?")
            params.append(end_date)
        if start_time:
            where_clauses.append("start_time >= ?")
            params.append(start_time)
        if end_time:
            where_clauses.append("end_time <= ?")
            params.append(end_time)
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        allowed = {"id", "date", "start_time", "end_time", "training_type", "rating"}
        if sort_by not in allowed:
            sort_by = "id"
        order = "DESC" if descending else "ASC"
        query += f" ORDER BY {sort_by} {order}"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        if offset is not None:
            if limit is None:
                query += " LIMIT -1"
            query += " OFFSET ?"
            params.append(offset)
        query += ";"
        return await self.fetch_all(query, tuple(params))

    async def delete(self, workout_id: int) -> None:
        rows = await super().fetch_all(
            "SELECT id FROM workouts WHERE id = ?;",
            (workout_id,),
        )
        if not rows:
            raise ValueError("workout not found")
        await self.execute("DELETE FROM workouts WHERE id = ?;", (workout_id,))

    async def fetch_detail(
        self, workout_id: int
    ) -> Tuple[
        int,
        str,
        Optional[str],
        Optional[str],
        Optional[str],
        str,
        str,
        Optional[str],
        Optional[str],
        Optional[str],
        Optional[int],
        Optional[int],
        Optional[int],
    ]:
        rows = await self.fetch_all(
            "SELECT id, date, name, start_time, end_time, timezone, training_type, notes, location, icon, rating, mood_before, mood_after FROM workouts WHERE id = ?;",
            (workout_id,),
        )
        if not rows:
            raise ValueError("workout not found")
        return rows[0]

    async def set_note(self, workout_id: int, note: str | None) -> None:
        await self.execute(
            "UPDATE workouts SET notes = ? WHERE id = ?;",
            (note, workout_id),
        )

    async def set_name(self, workout_id: int, name: str | None) -> None:
        await self.execute(
            "UPDATE workouts SET name = ? WHERE id = ?;",
            (name, workout_id),
        )

    async def set_start_time(self, workout_id: int, timestamp: str) -> None:
        await self.execute(
            "UPDATE workouts SET start_time = ? WHERE id = ?;",
            (timestamp, workout_id),
        )

    async def set_end_time(self, workout_id: int, timestamp: str) -> None:
        await self.execute(
            "UPDATE workouts SET end_time = ? WHERE id = ?;",
            (timestamp, workout_id),
        )

    async def set_training_type(self, workout_id: int, training_type: str) -> None:
        await self.execute(
            "UPDATE workouts SET training_type = ? WHERE id = ?;",
            (training_type, workout_id),
        )

    async def set_location(self, workout_id: int, location: Optional[str]) -> None:
        await self.execute(
            "UPDATE workouts SET location = ? WHERE id = ?;",
            (location, workout_id),
        )

    async def set_timezone(self, workout_id: int, timezone: str) -> None:
        await self.execute(
            "UPDATE workouts SET timezone = ? WHERE id = ?;",
            (timezone, workout_id),
        )

    async def set_rating(self, workout_id: int, rating: Optional[int]) -> None:
        await self.execute(
            "UPDATE workouts SET rating = ? WHERE id = ?;",
            (rating, workout_id),
        )

    async def set_mood_before(self, workout_id: int, mood: Optional[int]) -> None:
        await self.execute(
            "UPDATE workouts SET mood_before = ? WHERE id = ?;",
            (mood, workout_id),
        )

    async def set_mood_after(self, workout_id: int, mood: Optional[int]) -> None:
        await self.execute(
            "UPDATE workouts SET mood_after = ? WHERE id = ?;",
            (mood, workout_id),
        )

    async def set_icon(self, workout_id: int, icon: str | None) -> None:
        await self.execute(
            "UPDATE workouts SET icon = ? WHERE id = ?;",
            (icon, workout_id),
        )

    async def search(self, query: str) -> list[tuple[int, str]]:
        like = f"%{query.lower()}%"
        rows = await self.fetch_all(
            "SELECT id, date FROM workouts WHERE lower(notes) LIKE ? OR lower(location) LIKE ? ORDER BY id DESC;",
            (like, like),
        )
        return [(wid, date) for wid, date in rows]


class WorkoutRepository(BaseRepository):
    """Repository for workout table operations."""

    def create(
        self,
        date: str,
        name: str | None = None,
        timezone: str = "UTC",
        training_type: str = "strength",
        notes: str | None = None,
        location: str | None = None,
        rating: Optional[int] = None,
        mood_before: Optional[int] = None,
        mood_after: Optional[int] = None,
        icon: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> int:
        return self.execute(
            "INSERT INTO workouts (date, name, timezone, training_type, notes, location, icon, rating, mood_before, mood_after, start_time, end_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
            (
                date,
                name,
                timezone,
                training_type,
                notes,
                location,
                icon,
                rating,
                mood_before,
                mood_after,
                start_time,
                end_time,
            ),
        )

    def fetch_all_workouts(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        sort_by: str = "id",
        descending: bool = True,
        limit: int | None = None,
        offset: int | None = None,
    ) -> List[
        Tuple[
            int,
            str,
            Optional[str],
            Optional[str],
            Optional[str],
            str,
            str,
            Optional[str],
            Optional[str],
            Optional[str],
            Optional[int],
            Optional[int],
            Optional[int],
        ]
    ]:
        query = (
            "SELECT id, date, name, start_time, end_time, timezone, training_type, notes, location, icon, rating, mood_before, mood_after FROM workouts"
        )
        params: list[str | int] = []
        where_clauses: list[str] = []
        if start_date:
            where_clauses.append("date >= ?")
            params.append(start_date)
        if end_date:
            where_clauses.append("date <= ?")
            params.append(end_date)
        if start_time:
            where_clauses.append("start_time >= ?")
            params.append(start_time)
        if end_time:
            where_clauses.append("end_time <= ?")
            params.append(end_time)
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        allowed = {"id", "date", "start_time", "end_time", "training_type", "rating"}
        if sort_by not in allowed:
            sort_by = "id"
        order = "DESC" if descending else "ASC"
        query += f" ORDER BY {sort_by} {order}"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        if offset is not None:
            if limit is None:
                query += " LIMIT -1"
            query += " OFFSET ?"
            params.append(offset)
        query += ";"
        return self.fetch_all(query, tuple(params))

    def set_start_time(self, workout_id: int, timestamp: str) -> None:
        self.execute(
            "UPDATE workouts SET start_time = ? WHERE id = ?;",
            (timestamp, workout_id),
        )

    def set_end_time(self, workout_id: int, timestamp: str) -> None:
        self.execute(
            "UPDATE workouts SET end_time = ? WHERE id = ?;",
            (timestamp, workout_id),
        )

    def set_training_type(self, workout_id: int, training_type: str) -> None:
        self.execute(
            "UPDATE workouts SET training_type = ? WHERE id = ?;",
            (training_type, workout_id),
        )

    def set_location(self, workout_id: int, location: Optional[str]) -> None:
        self.execute(
            "UPDATE workouts SET location = ? WHERE id = ?;",
            (location, workout_id),
        )

    def set_timezone(self, workout_id: int, timezone: str) -> None:
        self.execute(
            "UPDATE workouts SET timezone = ? WHERE id = ?;",
            (timezone, workout_id),
        )

    def set_rating(self, workout_id: int, rating: Optional[int]) -> None:
        self.execute(
            "UPDATE workouts SET rating = ? WHERE id = ?;",
            (rating, workout_id),
        )

    def set_mood_before(self, workout_id: int, mood: Optional[int]) -> None:
        self.execute(
            "UPDATE workouts SET mood_before = ? WHERE id = ?;",
            (mood, workout_id),
        )

    def set_mood_after(self, workout_id: int, mood: Optional[int]) -> None:
        self.execute(
            "UPDATE workouts SET mood_after = ? WHERE id = ?;",
            (mood, workout_id),
        )

    def workout_duration(self, workout_id: int) -> float | None:
        rows = self.fetch_all(
            "SELECT start_time, end_time FROM workouts WHERE id = ?;",
            (workout_id,),
        )
        if not rows:
            return None
        start, end = rows[0]
        if not start or not end:
            return None
        t0 = datetime.datetime.fromisoformat(start)
        t1 = datetime.datetime.fromisoformat(end)
        return (t1 - t0).total_seconds()

    def fetch_ratings(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Tuple[str, int]]:
        """Return all workout ratings within optional date range."""
        query = "SELECT date, rating FROM workouts WHERE rating IS NOT NULL"
        params: list[str] = []
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        query += " ORDER BY date;"
        rows = self.fetch_all(query, tuple(params))
        return [(d, int(r)) for d, r in rows]

    def fetch_detail(self, workout_id: int) -> Tuple[
        int,
        str,
        Optional[str],
        Optional[str],
        Optional[str],
        str,
        str,
        Optional[str],
        Optional[str],
        Optional[str],
        Optional[int],
        Optional[int],
        Optional[int],
    ]:
        rows = self.fetch_all(
            "SELECT id, date, name, start_time, end_time, timezone, training_type, notes, location, icon, rating, mood_before, mood_after FROM workouts WHERE id = ?;",
            (workout_id,),
        )
        if not rows:
            raise ValueError("workout not found")
        return rows[0]

    def set_note(self, workout_id: int, note: str | None) -> None:
        self.execute(
            "UPDATE workouts SET notes = ? WHERE id = ?;",
            (note, workout_id),
        )

    def set_name(self, workout_id: int, name: str | None) -> None:
        self.execute(
            "UPDATE workouts SET name = ? WHERE id = ?;",
            (name, workout_id),
        )

    def search(self, query: str) -> list[tuple[int, str]]:
        """Return workouts where notes or location match the query."""
        like = f"%{query.lower()}%"
        rows = self.fetch_all(
            "SELECT id, date FROM workouts WHERE lower(notes) LIKE ? OR lower(location) LIKE ? ORDER BY id DESC;",
            (like, like),
        )
        return [(wid, date) for wid, date in rows]

    def delete_all(self) -> None:
        self._delete_all("workouts")

    def delete(self, workout_id: int) -> None:
        rows = super().fetch_all(
            "SELECT id FROM workouts WHERE id = ?;",
            (workout_id,),
        )
        if not rows:
            raise ValueError("workout not found")
        self.execute("DELETE FROM workouts WHERE id = ?;", (workout_id,))

    def delete_empty(self) -> None:
        """Remove workouts that have no exercises."""
        self.execute(
            "DELETE FROM workouts WHERE id NOT IN (SELECT DISTINCT workout_id FROM exercises);"
        )

    def set_icon(self, workout_id: int, icon: str | None) -> None:
        self.execute(
            "UPDATE workouts SET icon = ? WHERE id = ?;",
            (icon, workout_id),
        )

    def monthly_counts(self) -> List[Tuple[str, int]]:
        rows = self.fetch_all(
            "SELECT substr(date,1,7) AS m, COUNT(*) FROM workouts GROUP BY m ORDER BY m;"
        )
        return [(m, int(c)) for m, c in rows]


class ExerciseRepository(BaseRepository):
    """Repository for exercise table operations."""

    def __init__(self, db_path: str = "workout.db") -> None:
        super().__init__(db_path)
        self.exercise_names = ExerciseNameRepository(db_path)

    def add(
        self,
        workout_id: int,
        name: str,
        equipment_name: Optional[str] = None,
        note: Optional[str] = None,
    ) -> int:
        self.exercise_names.ensure([name])
        return self.execute(
            "INSERT INTO exercises (workout_id, name, equipment_name, note) VALUES (?, ?, ?, ?);",
            (workout_id, name, equipment_name, note),
        )

    def remove(self, exercise_id: int) -> None:
        self.execute("DELETE FROM exercises WHERE id = ?;", (exercise_id,))

    def fetch_for_workout(
        self, workout_id: int
    ) -> List[Tuple[int, str, Optional[str], Optional[str]]]:
        return self.fetch_all(
            "SELECT id, name, equipment_name, note FROM exercises WHERE workout_id = ?;",
            (workout_id,),
        )

    def fetch_detail(
        self, exercise_id: int
    ) -> Tuple[int, str, Optional[str], Optional[str]]:
        rows = self.fetch_all(
            "SELECT workout_id, name, equipment_name, note FROM exercises WHERE id = ?;",
            (exercise_id,),
        )
        if not rows:
            raise ValueError("exercise not found")
        return rows[0]

    def update_note(self, exercise_id: int, note: Optional[str]) -> None:
        self.execute(
            "UPDATE exercises SET note = ? WHERE id = ?;",
            (note, exercise_id),
        )

    def update_name(self, exercise_id: int, name: str) -> None:
        self.exercise_names.ensure([name])
        self.execute(
            "UPDATE exercises SET name = ? WHERE id = ?;",
            (name, exercise_id),
        )


class AsyncExerciseRepository(AsyncBaseRepository):
    """Asynchronous repository for exercises."""

    def __init__(self, db_path: str = "workout.db") -> None:
        super().__init__(db_path)
        self.exercise_names = ExerciseNameRepository(db_path)

    async def add(
        self,
        workout_id: int,
        name: str,
        equipment_name: Optional[str] = None,
        note: Optional[str] = None,
    ) -> int:
        self.exercise_names.ensure([name])
        return await self.execute(
            "INSERT INTO exercises (workout_id, name, equipment_name, note) VALUES (?, ?, ?, ?);",
            (workout_id, name, equipment_name, note),
        )

    async def remove(self, exercise_id: int) -> None:
        await self.execute("DELETE FROM exercises WHERE id = ?;", (exercise_id,))

    async def fetch_for_workout(
        self, workout_id: int
    ) -> List[Tuple[int, str, Optional[str], Optional[str]]]:
        return await self.fetch_all(
            "SELECT id, name, equipment_name, note FROM exercises WHERE workout_id = ?;",
            (workout_id,),
        )

    async def fetch_detail(
        self, exercise_id: int
    ) -> Tuple[int, str, Optional[str], Optional[str]]:
        rows = await self.fetch_all(
            "SELECT workout_id, name, equipment_name, note FROM exercises WHERE id = ?;",
            (exercise_id,),
        )
        if not rows:
            raise ValueError("exercise not found")
        return rows[0]

    async def update_note(self, exercise_id: int, note: Optional[str]) -> None:
        await self.execute(
            "UPDATE exercises SET note = ? WHERE id = ?;",
            (note, exercise_id),
        )

    async def update_name(self, exercise_id: int, name: str) -> None:
        self.exercise_names.ensure([name])
        await self.execute(
            "UPDATE exercises SET name = ? WHERE id = ?;",
            (name, exercise_id),
        )


class SetRepository(BaseRepository):
    """Repository for sets table operations."""

    def __init__(self, db_path: str, settings: Optional["SettingsRepository"] = None) -> None:
        super().__init__(db_path)
        self.settings = settings

    @staticmethod
    def _velocity(reps: int, start: Optional[str], end: Optional[str]) -> float:
        if not start or not end or reps <= 0:
            return 0.0
        t0 = datetime.datetime.fromisoformat(start)
        t1 = datetime.datetime.fromisoformat(end)
        secs = (t1 - t0).total_seconds()
        return (reps * 0.5) / secs if secs > 0 else 0.0

    def add(
        self,
        exercise_id: int,
        reps: int,
        weight: float,
        rpe: int,
        note: Optional[str] = None,
        planned_set_id: Optional[int] = None,
        diff_reps: int = 0,
        diff_weight: float = 0.0,
        diff_rpe: int = 0,
        warmup: bool = False,
    ) -> int:
        if reps <= 0:
            raise ValueError("reps must be positive")
        if weight < 0:
            raise ValueError("weight must be non-negative")
        max_rpe = 10
        if self.settings is not None:
            max_rpe = self.settings.get_int("rpe_scale", 10)
        if rpe < 0 or rpe > max_rpe:
            raise ValueError(f"rpe must be between 0 and {max_rpe}")
        rows = self.fetch_all(
            "SELECT COALESCE(MAX(position), 0) + 1 FROM sets WHERE exercise_id = ?;",
            (exercise_id,),
        )
        position = int(rows[0][0]) if rows else 1
        return self.execute(
            "INSERT INTO sets (exercise_id, reps, weight, rpe, note, planned_set_id, diff_reps, diff_weight, diff_rpe, warmup, position) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
            (
                exercise_id,
                reps,
                weight,
                rpe,
                note,
                planned_set_id,
                diff_reps,
                diff_weight,
                diff_rpe,
                int(warmup),
                position,
            ),
        )

    def bulk_add(
        self, exercise_id: int, entries: Iterable[tuple[int, float, int]]
    ) -> list[int]:
        ids: list[int] = []
        for reps, weight, rpe in entries:
            ids.append(self.add(exercise_id, reps, weight, rpe, None))
        return ids

    def update(
        self, set_id: int, reps: int, weight: float, rpe: int, warmup: bool | None = None
    ) -> None:
        if reps <= 0:
            raise ValueError("reps must be positive")
        if weight < 0:
            raise ValueError("weight must be non-negative")
        max_rpe = 10
        if self.settings is not None:
            max_rpe = self.settings.get_int("rpe_scale", 10)
        if rpe < 0 or rpe > max_rpe:
            raise ValueError(f"rpe must be between 0 and {max_rpe}")
        row = self.fetch_all("SELECT planned_set_id FROM sets WHERE id = ?;", (set_id,))
        diff_reps = 0
        diff_weight = 0.0
        diff_rpe = 0
        if row and row[0][0] is not None:
            planned_id = row[0][0]
            plan = self.fetch_all(
                "SELECT reps, weight, rpe FROM planned_sets WHERE id = ?;",
                (planned_id,),
            )
            if plan:
                diff_reps = reps - int(plan[0][0])
                diff_weight = weight - float(plan[0][1])
                diff_rpe = rpe - int(plan[0][2])
        query = (
            "UPDATE sets SET reps = ?, weight = ?, rpe = ?, diff_reps = ?, diff_weight = ?, diff_rpe = ?"
        )
        params = [reps, weight, rpe, diff_reps, diff_weight, diff_rpe]
        if warmup is not None:
            query += ", warmup = ?"
            params.append(int(warmup))
        query += " WHERE id = ?;"
        params.append(set_id)
        self.execute(query, tuple(params))

    def bulk_update(self, updates: Iterable[dict]) -> None:
        """Update multiple sets in one transaction."""
        for upd in updates:
            sid = int(upd.get("id"))
            reps = int(upd.get("reps"))
            weight = float(upd.get("weight"))
            rpe = int(upd.get("rpe"))
            warmup_val = upd.get("warmup")
            warm = bool(warmup_val) if warmup_val is not None else None
            self.update(sid, reps, weight, rpe, warm)

    def remove(self, set_id: int) -> None:
        self.execute("DELETE FROM sets WHERE id = ?;", (set_id,))

    def reorder_sets(self, exercise_id: int, order: list[int]) -> None:
        existing = [
            row[0]
            for row in self.fetch_all(
                "SELECT id FROM sets WHERE exercise_id = ? ORDER BY position;",
                (exercise_id,),
            )
        ]
        if set(order) != set(existing) or len(order) != len(existing):
            raise ValueError("invalid order")
        for pos, sid in enumerate(order, start=1):
            self.execute(
                "UPDATE sets SET position = ? WHERE id = ?;",
                (pos, sid),
            )

    def set_start_time(self, set_id: int, timestamp: str) -> None:
        self.execute(
            "UPDATE sets SET start_time = ? WHERE id = ?;",
            (timestamp, set_id),
        )

    def set_end_time(self, set_id: int, timestamp: str) -> None:
        self.execute(
            "UPDATE sets SET end_time = ? WHERE id = ?;",
            (timestamp, set_id),
        )

    def bulk_complete(self, set_ids: list[int], timestamp: str) -> None:
        if not set_ids:
            return
        with self._connection() as conn:
            for sid in set_ids:
                conn.execute(
                    "UPDATE sets SET start_time = ?, end_time = ? WHERE id = ?;",
                    (timestamp, timestamp, sid),
                )

    def set_duration(self, set_id: int, seconds: float, end_timestamp: str | None = None) -> None:
        if seconds <= 0:
            raise ValueError("seconds must be positive")
        end_dt = (
            datetime.datetime.now()
            if end_timestamp is None
            else datetime.datetime.fromisoformat(end_timestamp)
        )
        start_dt = end_dt - datetime.timedelta(seconds=float(seconds))
        self.set_start_time(set_id, start_dt.isoformat(timespec="seconds"))
        self.set_end_time(set_id, end_dt.isoformat(timespec="seconds"))

    def update_note(self, set_id: int, note: Optional[str]) -> None:
        self.execute(
            "UPDATE sets SET note = ? WHERE id = ?;",
            (note, set_id),
        )

    def set_rest_note(self, set_id: int, rest_note: Optional[str]) -> None:
        """Store rest note for a set."""
        self.execute(
            "UPDATE sets SET rest_note = ? WHERE id = ?;",
            (rest_note, set_id),
        )

    def fetch_exercise_id(self, set_id: int) -> int:
        rows = self.fetch_all(
            "SELECT exercise_id FROM sets WHERE id = ?;",
            (set_id,),
        )
        if not rows:
            raise ValueError("set not found")
        return int(rows[0][0])

    def fetch_for_exercise(
        self, exercise_id: int
    ) -> List[Tuple[int, int, float, int, Optional[str], Optional[str], Optional[str], int, int]]:
        return self.fetch_all(
            "SELECT id, reps, weight, rpe, start_time, end_time, rest_note, warmup, position FROM sets WHERE exercise_id = ? ORDER BY position;",
            (exercise_id,),
        )

    def fetch_detail(self, set_id: int) -> dict:
        rows = self.fetch_all(
            "SELECT id, reps, weight, rpe, note, rest_note, planned_set_id, diff_reps, diff_weight, diff_rpe, start_time, end_time, warmup, position FROM sets WHERE id = ?;",
            (set_id,),
        )
        (
            sid,
            reps,
            weight,
            rpe,
            note,
            rest_note,
            planned_set_id,
            diff_reps,
            diff_weight,
            diff_rpe,
            start_time,
            end_time,
            warmup,
            position,
        ) = rows[0]
        velocity = self._velocity(int(reps), start_time, end_time)
        return {
            "id": sid,
            "reps": reps,
            "weight": weight,
            "rpe": rpe,
            "planned_set_id": planned_set_id,
            "diff_reps": diff_reps,
            "diff_weight": diff_weight,
            "diff_rpe": diff_rpe,
            "start_time": start_time,
            "end_time": end_time,
            "note": note,
            "rest_note": rest_note,
            "warmup": bool(warmup),
            "position": position,
            "velocity": velocity,
        }

    def last_rpe(self, exercise_id: int) -> int | None:
        rows = self.fetch_all(
            "SELECT rpe FROM sets WHERE exercise_id = ? ORDER BY id DESC LIMIT 1;",
            (exercise_id,),
        )
        return int(rows[0][0]) if rows else None

    def previous_rpe(self, set_id: int) -> int | None:
        ex_rows = self.fetch_all(
            "SELECT exercise_id FROM sets WHERE id = ?;",
            (set_id,),
        )
        if not ex_rows:
            return None
        ex_id = int(ex_rows[0][0])
        rows = self.fetch_all(
            "SELECT rpe FROM sets WHERE exercise_id = ? AND id < ? ORDER BY id DESC LIMIT 1;",
            (ex_id, set_id),
        )
        return int(rows[0][0]) if rows else None

    def fetch_history_by_names(
        self,
        names: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        equipment: Optional[List[str]] = None,
        with_equipment: bool = False,
        with_duration: bool = False,
        with_workout_id: bool = False,
        with_location: bool = False,
    ) -> List[Tuple]:
        placeholders = ", ".join(["?" for _ in names])
        select = "SELECT s.reps, s.weight, s.rpe, w.date"
        if with_equipment:
            select += ", e.name, e.equipment_name"
        if with_duration:
            select += ", s.start_time, s.end_time"
        if with_workout_id:
            select += ", w.id"
        if with_location:
            select += ", w.location"
        query = (
            f"{select} FROM sets s "
            "JOIN exercises e ON s.exercise_id = e.id "
            "JOIN workouts w ON e.workout_id = w.id "
            f"WHERE e.name IN ({placeholders})"
        )
        params: List[str] = list(names)
        if equipment:
            eq_placeholders = ", ".join(["?" for _ in equipment])
            query += f" AND e.equipment_name IN ({eq_placeholders})"
            params.extend(equipment)
        if start_date:
            query += " AND w.date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND w.date <= ?"
            params.append(end_date)
        query += " ORDER BY w.date, s.id;"
        return self.fetch_all(query, tuple(params))

    def fetch_for_workout(
        self, workout_id: int
    ) -> List[Tuple[str, Optional[str], int, float, int, Optional[str], Optional[str]]]:
        return self.fetch_all(
            "SELECT e.name, e.equipment_name, s.reps, s.weight, s.rpe,"
            " s.start_time, s.end_time "
            "FROM sets s JOIN exercises e ON s.exercise_id = e.id "
            "WHERE e.workout_id = ? ORDER BY e.id, s.position;",
            (workout_id,),
        )

    def export_workout_csv(self, workout_id: int) -> str:
        rows = self.fetch_for_workout(workout_id)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "Exercise",
                "Equipment",
                "Reps",
                "Weight",
                "RPE",
                "Start",
                "End",
            ]
        )
        for name, eq, reps, weight, rpe, start, end in rows:
            writer.writerow(
                [
                    name,
                    eq or "",
                    reps,
                    weight,
                    rpe,
                    start or "",
                    end or "",
                ]
            )
        return output.getvalue()

    def export_workout_json(self, workout_id: int) -> str:
        """Return sets for a workout as a JSON string."""
        rows = self.fetch_for_workout(workout_id)
        data = [
            {
                "exercise": name,
                "equipment": eq,
                "reps": int(reps),
                "weight": float(weight),
                "rpe": int(rpe),
                "start": start,
                "end": end,
            }
            for name, eq, reps, weight, rpe, start, end in rows
        ]
        return json.dumps(data)

    def export_workout_xml(self, workout_id: int) -> str:
        """Return sets for a workout as an XML string."""
        rows = self.fetch_for_workout(workout_id)
        from xml.etree.ElementTree import Element, SubElement, tostring

        root = Element("workout", id=str(workout_id))
        for name, eq, reps, weight, rpe, start, end in rows:
            set_elem = SubElement(root, "set")
            SubElement(set_elem, "exercise").text = name
            if eq:
                SubElement(set_elem, "equipment").text = eq
            SubElement(set_elem, "reps").text = str(reps)
            SubElement(set_elem, "weight").text = str(weight)
            SubElement(set_elem, "rpe").text = str(rpe)
            if start:
                SubElement(set_elem, "start").text = start
            if end:
                SubElement(set_elem, "end").text = end
        return tostring(root, encoding="unicode")

    def workout_summary(self, workout_id: int) -> dict:
        rows = self.fetch_for_workout(workout_id)
        volume = 0.0
        rpe_total = 0
        count = 0
        for _name, _eq, reps, weight, rpe, _s, _e in rows:
            volume += int(reps) * float(weight)
            rpe_total += int(rpe)
            count += 1
        avg_rpe = rpe_total / count if count else 0.0
        return {
            "volume": round(volume, 2),
            "sets": count,
            "avg_rpe": round(avg_rpe, 2),
        }

    def planned_completion(self, plan_id: int) -> float:
        total_rows = self.fetch_all(
            "SELECT COUNT(*) FROM planned_sets ps JOIN planned_exercises pe ON ps.planned_exercise_id = pe.id WHERE pe.planned_workout_id = ?;",
            (plan_id,),
        )
        total = int(total_rows[0][0]) if total_rows else 0
        if total == 0:
            return 0.0
        logged_rows = self.fetch_all(
            "SELECT COUNT(*) FROM sets s JOIN planned_sets ps ON s.planned_set_id = ps.id JOIN planned_exercises pe ON ps.planned_exercise_id = pe.id WHERE pe.planned_workout_id = ?;",
            (plan_id,),
        )
        logged = int(logged_rows[0][0]) if logged_rows else 0
        return round(100 * logged / total, 2)

    def recent_equipment(self, limit: int = 5) -> list[str]:
        """Return recently used equipment names ordered by recency."""
        rows = self.fetch_all(
            """
            SELECT e.equipment_name FROM sets s
            JOIN exercises e ON s.exercise_id = e.id
            JOIN workouts w ON e.workout_id = w.id
            WHERE e.equipment_name IS NOT NULL
            ORDER BY w.date DESC, s.id DESC LIMIT ?;
            """,
            (limit,),
        )
        result: list[str] = []
        for r in rows:
            name = r[0]
            if name and name not in result:
                result.append(name)
        return result


class PlannedWorkoutRepository(BaseRepository):
    """Repository for planned workouts."""

    def create(self, date: str, training_type: str = "strength") -> int:
        rows = self.fetch_all("SELECT COALESCE(MAX(position),0)+1 FROM planned_workouts")
        pos = int(rows[0][0]) if rows else 1
        return self.execute(
            "INSERT INTO planned_workouts (date, training_type, position) VALUES (?, ?, ?);",
            (date, training_type, pos),
        )

    def fetch_all(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        sort_by: str = "position",
        descending: bool = True,
    ) -> List[Tuple[int, str, str, int]]:
        query = "SELECT id, date, training_type, position FROM planned_workouts WHERE 1=1"
        params: list[str] = []
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        allowed = {"id", "date", "training_type", "position"}
        if sort_by not in allowed:
            sort_by = "position"
        order = "DESC" if descending else "ASC"
        query += f" ORDER BY {sort_by} {order};"
        return super().fetch_all(query, tuple(params))

    def search(
        self,
        query_str: str | None = None,
        training_type: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> List[Tuple[int, str, str, int]]:
        query = "SELECT id, date, training_type, position FROM planned_workouts WHERE 1=1"
        params: list[str] = []
        if query_str:
            query += " AND lower(training_type) LIKE ?"
            params.append(f"%{query_str.lower()}%")
        if training_type:
            query += " AND training_type = ?"
            params.append(training_type)
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        query += " ORDER BY position ASC;"
        return super().fetch_all(query, tuple(params))

    def fetch_detail(self, plan_id: int) -> Tuple[int, str, str]:
        rows = super().fetch_all(
            "SELECT id, date, training_type FROM planned_workouts WHERE id = ?;",
            (plan_id,),
        )
        if not rows:
            raise ValueError("planned workout not found")
        return rows[0]

    def update_date(self, plan_id: int, date: str) -> None:
        rows = super().fetch_all(
            "SELECT id FROM planned_workouts WHERE id = ?;",
            (plan_id,),
        )
        if not rows:
            raise ValueError("planned workout not found")
        self.execute(
            "UPDATE planned_workouts SET date = ? WHERE id = ?;",
            (date, plan_id),
        )

    def set_training_type(self, plan_id: int, training_type: str) -> None:
        rows = super().fetch_all(
            "SELECT id FROM planned_workouts WHERE id = ?;",
            (plan_id,),
        )
        if not rows:
            raise ValueError("planned workout not found")
        self.execute(
            "UPDATE planned_workouts SET training_type = ? WHERE id = ?;",
            (training_type, plan_id),
        )

    def delete(self, plan_id: int) -> None:
        rows = super().fetch_all(
            "SELECT id FROM planned_workouts WHERE id = ?;",
            (plan_id,),
        )
        if not rows:
            raise ValueError("planned workout not found")
        self.execute("DELETE FROM planned_workouts WHERE id = ?;", (plan_id,))

    def delete_bulk(self, plan_ids: list[int]) -> None:
        if not plan_ids:
            return
        placeholders = ",".join("?" for _ in plan_ids)
        self.execute(
            f"DELETE FROM planned_workouts WHERE id IN ({placeholders});",
            tuple(plan_ids),
        )

    def delete_all(self) -> None:
        self._delete_all("planned_workouts")

    def reorder(self, order: list[int]) -> None:
        existing = [row[0] for row in super().fetch_all("SELECT id FROM planned_workouts ORDER BY position;")]
        if set(order) != set(existing) or len(order) != len(existing):
            raise ValueError("invalid order")
        for pos, pid in enumerate(order, start=1):
            self.execute(
                "UPDATE planned_workouts SET position = ? WHERE id = ?;",
                (pos, pid),
            )


class PlannedExerciseRepository(BaseRepository):
    """Repository for planned exercises."""

    def add(
        self, workout_id: int, name: str, equipment_name: Optional[str] = None
    ) -> int:
        return self.execute(
            "INSERT INTO planned_exercises (planned_workout_id, name, equipment_name) VALUES (?, ?, ?);",
            (workout_id, name, equipment_name),
        )

    def remove(self, exercise_id: int) -> None:
        self.execute(
            "DELETE FROM planned_exercises WHERE id = ?;",
            (exercise_id,),
        )

    def fetch_for_workout(
        self, workout_id: int
    ) -> List[Tuple[int, str, Optional[str]]]:
        return super().fetch_all(
            "SELECT id, name, equipment_name FROM planned_exercises WHERE planned_workout_id = ?;",
            (workout_id,),
        )


class PlannedSetRepository(BaseRepository):
    """Repository for planned sets."""

    def __init__(self, db_path: str = "workout.db", settings: Optional["SettingsRepository"] = None) -> None:
        super().__init__(db_path)
        self.settings = settings

    def add(self, exercise_id: int, reps: int, weight: float, rpe: int) -> int:
        max_rpe = 10
        if self.settings is not None:
            max_rpe = self.settings.get_int("rpe_scale", 10)
        if rpe < 0 or rpe > max_rpe:
            raise ValueError(f"rpe must be between 0 and {max_rpe}")
        return self.execute(
            "INSERT INTO planned_sets (planned_exercise_id, reps, weight, rpe) VALUES (?, ?, ?, ?);",
            (exercise_id, reps, weight, rpe),
        )

    def remove(self, set_id: int) -> None:
        self.execute("DELETE FROM planned_sets WHERE id = ?;", (set_id,))

    def fetch_for_exercise(self, exercise_id: int) -> List[Tuple[int, int, float, int]]:
        return super().fetch_all(
            "SELECT id, reps, weight, rpe FROM planned_sets WHERE planned_exercise_id = ?;",
            (exercise_id,),
        )

    def update(self, set_id: int, reps: int, weight: float, rpe: int) -> None:
        max_rpe = 10
        if self.settings is not None:
            max_rpe = self.settings.get_int("rpe_scale", 10)
        if rpe < 0 or rpe > max_rpe:
            raise ValueError(f"rpe must be between 0 and {max_rpe}")
        self.execute(
            "UPDATE planned_sets SET reps = ?, weight = ?, rpe = ? WHERE id = ?;",
            (reps, weight, rpe, set_id),
        )

    def fetch_detail(self, set_id: int) -> dict:
        rows = self.fetch_all(
            "SELECT id, planned_exercise_id, reps, weight, rpe FROM planned_sets WHERE id = ?;",
            (set_id,),
        )
        if not rows:
            raise ValueError("planned set not found")
        sid, ex_id, reps, weight, rpe = rows[0]
        return {
            "id": sid,
            "planned_exercise_id": ex_id,
            "reps": reps,
            "weight": weight,
            "rpe": rpe,
        }


class MuscleRepository(BaseRepository):
    """Repository for muscle alias management."""

    def ensure(self, muscles: Iterable[str]) -> None:
        with self._connection() as conn:
            for m in muscles:
                conn.execute(
                    "INSERT OR IGNORE INTO muscles (name, canonical_name) VALUES (?, ?);",
                    (m, m),
                )

    def fetch_all(self) -> List[str]:
        rows = super().fetch_all("SELECT name FROM muscles ORDER BY name;")
        return [r[0] for r in rows]

    def fuzzy_search(self, query: str, limit: int = 5) -> List[str]:
        """Return muscle names closest to the query."""
        names = self.fetch_all()
        return difflib.get_close_matches(query, names, n=limit, cutoff=0.3)

    def canonical(self, name: str) -> str:
        rows = super().fetch_all(
            "SELECT canonical_name FROM muscles WHERE name = ?;", (name,)
        )
        return rows[0][0] if rows else name

    def aliases(self, name: str) -> List[str]:
        canonical = self.canonical(name)
        rows = super().fetch_all(
            "SELECT name FROM muscles WHERE canonical_name = ? ORDER BY name;",
            (canonical,),
        )
        return [r[0] for r in rows]

    def link(self, name1: str, name2: str) -> None:
        self.ensure([name1, name2])
        canon1 = self.canonical(name1)
        canon2 = self.canonical(name2)
        if canon1 == canon2:
            return
        with self._connection() as conn:
            conn.execute(
                "UPDATE muscles SET canonical_name = ? WHERE canonical_name = ?;",
                (canon1, canon2),
            )

    def add_alias(self, new_name: str, existing: str) -> None:
        self.ensure([existing])
        canonical = self.canonical(existing)
        with self._connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO muscles (name, canonical_name) VALUES (?, ?);",
                (new_name, canonical),
            )

    def add(self, name: str) -> None:
        rows = super().fetch_all(
            "SELECT canonical_name FROM muscles WHERE name = ?;",
            (name,),
        )
        if rows:
            if rows[0][0] == name:
                raise ValueError("muscle exists")
            raise ValueError("name is alias")
        with self._connection() as conn:
            conn.execute(
                "INSERT INTO muscles (name, canonical_name) VALUES (?, ?);",
                (name, name),
            )


class MuscleGroupRepository(BaseRepository):
    """Repository for muscle group management."""

    def __init__(self, db_path: str = "workout.db", muscles: Optional[MuscleRepository] = None) -> None:
        super().__init__(db_path)
        self.muscles = muscles or MuscleRepository(db_path)

    def add(self, name: str) -> None:
        rows = super().fetch_all("SELECT name FROM muscle_groups WHERE name = ?;", (name,))
        if rows:
            raise ValueError("group exists")
        self.execute("INSERT INTO muscle_groups (name) VALUES (?);", (name,))

    def rename(self, name: str, new_name: str) -> None:
        rows = super().fetch_all("SELECT name FROM muscle_groups WHERE name = ?;", (name,))
        if not rows:
            raise ValueError("group not found")
        if new_name != name and super().fetch_all(
            "SELECT name FROM muscle_groups WHERE name = ?;", (new_name,)
        ):
            raise ValueError("target exists")
        with self._connection() as conn:
            if new_name != name:
                conn.execute(
                    "UPDATE muscle_groups SET name = ? WHERE name = ?;",
                    (new_name, name),
                )
                conn.execute(
                    "UPDATE muscle_group_members SET group_name = ? WHERE group_name = ?;",
                    (new_name, name),
                )

    def delete(self, name: str) -> None:
        rows = super().fetch_all("SELECT name FROM muscle_groups WHERE name = ?;", (name,))
        if not rows:
            raise ValueError("group not found")
        with self._connection() as conn:
            conn.execute("DELETE FROM muscle_groups WHERE name = ?;", (name,))
            conn.execute("DELETE FROM muscle_group_members WHERE group_name = ?;", (name,))

    def fetch_all(self) -> List[str]:
        rows = super().fetch_all("SELECT name FROM muscle_groups ORDER BY name;")
        return [r[0] for r in rows]

    def assign(self, group: str, muscle: str) -> None:
        if not super().fetch_all("SELECT name FROM muscle_groups WHERE name = ?;", (group,)):
            raise ValueError("group not found")
        self.muscles.ensure([muscle])
        canon = self.muscles.canonical(muscle)
        with self._connection() as conn:
            conn.execute(
                "DELETE FROM muscle_group_members WHERE muscle_name = ?;", (canon,)
            )
            conn.execute(
                "INSERT INTO muscle_group_members (muscle_name, group_name) VALUES (?, ?);",
                (canon, group),
            )

    def remove_assignment(self, muscle: str) -> None:
        canon = self.muscles.canonical(muscle)
        self.execute("DELETE FROM muscle_group_members WHERE muscle_name = ?;", (canon,))

    def set_members(self, group: str, muscles: List[str]) -> None:
        self.fetch_all()  # Ensure table exists
        for m in muscles:
            self.muscles.ensure([m])
        with self._connection() as conn:
            conn.execute(
                "DELETE FROM muscle_group_members WHERE group_name = ?;", (group,)
            )
            for m in muscles:
                canon = self.muscles.canonical(m)
                conn.execute(
                    "DELETE FROM muscle_group_members WHERE muscle_name = ?;", (canon,)
                )
                conn.execute(
                    "INSERT INTO muscle_group_members (muscle_name, group_name) VALUES (?, ?);",
                    (canon, group),
                )

    def fetch_muscles(self, group: str) -> List[str]:
        rows = super().fetch_all(
            "SELECT muscle_name FROM muscle_group_members WHERE group_name = ? ORDER BY muscle_name;",
            (group,),
        )
        return [r[0] for r in rows]

    def fetch_group(self, muscle: str) -> Optional[str]:
        canon = self.muscles.canonical(muscle)
        rows = super().fetch_all(
            "SELECT group_name FROM muscle_group_members WHERE muscle_name = ?;",
            (canon,),
        )
        return rows[0][0] if rows else None


class ExerciseNameRepository(BaseRepository):
    """Repository for exercise alias management."""

    def ensure(self, names: Iterable[str]) -> None:
        with self._connection() as conn:
            for n in names:
                conn.execute(
                    "INSERT OR IGNORE INTO exercise_names (name, canonical_name) VALUES (?, ?);",
                    (n, n),
                )

    def fetch_all(self) -> List[str]:
        rows = super().fetch_all("SELECT name FROM exercise_names ORDER BY name;")
        return [r[0] for r in rows]

    def canonical(self, name: str) -> str:
        rows = super().fetch_all(
            "SELECT canonical_name FROM exercise_names WHERE name = ?;",
            (name,),
        )
        return rows[0][0] if rows else name

    def aliases(self, name: str) -> List[str]:
        canonical = self.canonical(name)
        rows = super().fetch_all(
            "SELECT name FROM exercise_names WHERE canonical_name = ? ORDER BY name;",
            (canonical,),
        )
        return [r[0] for r in rows]

    def link(self, name1: str, name2: str) -> None:
        self.ensure([name1, name2])
        canon1 = self.canonical(name1)
        canon2 = self.canonical(name2)
        if canon1 == canon2:
            return
        with self._connection() as conn:
            conn.execute(
                "UPDATE exercise_names SET canonical_name = ? WHERE canonical_name = ?;",
                (canon1, canon2),
            )

    def add_alias(self, new_name: str, existing: str) -> None:
        self.ensure([existing])
        canonical = self.canonical(existing)
        with self._connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO exercise_names (name, canonical_name) VALUES (?, ?);",
                (new_name, canonical),
            )

    def remove_alias(self, alias: str) -> None:
        """Delete an alias without affecting the canonical name."""
        canonical = self.canonical(alias)
        if alias == canonical:
            raise ValueError("cannot remove canonical name")
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT name FROM exercise_names WHERE name = ?;",
                (alias,),
            ).fetchall()
            if not rows:
                raise ValueError("alias not found")
            conn.execute(
                "DELETE FROM exercise_names WHERE name = ?;",
                (alias,),
            )

    def search(self, query: str, limit: int = 5) -> List[str]:
        """Return exercise names matching the query."""
        like = f"%{query.lower()}%"
        rows = super().fetch_all(
            "SELECT name FROM exercise_names WHERE lower(name) LIKE ? ORDER BY name LIMIT ?;",
            (like, limit),
        )
        return [r[0] for r in rows]


class ExerciseVariantRepository(BaseRepository):
    """Repository managing exercise variant links."""

    def __init__(self, db_path: str = "workout.db") -> None:
        super().__init__(db_path)
        self.exercise_names = ExerciseNameRepository(db_path)

    def link(self, exercise: str, variant: str) -> None:
        self.exercise_names.ensure([exercise, variant])
        ex = self.exercise_names.canonical(exercise)
        var = self.exercise_names.canonical(variant)
        if ex == var:
            return
        with self._connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO exercise_variants (exercise_name, variant_name) VALUES (?, ?);",
                (ex, var),
            )
            conn.execute(
                "INSERT OR IGNORE INTO exercise_variants (exercise_name, variant_name) VALUES (?, ?);",
                (var, ex),
            )

    def unlink(self, exercise: str, variant: str) -> None:
        ex = self.exercise_names.canonical(exercise)
        var = self.exercise_names.canonical(variant)
        with self._connection() as conn:
            conn.execute(
                "DELETE FROM exercise_variants WHERE exercise_name = ? AND variant_name = ?;",
                (ex, var),
            )
            conn.execute(
                "DELETE FROM exercise_variants WHERE exercise_name = ? AND variant_name = ?;",
                (var, ex),
            )

    def fetch_variants(self, exercise: str) -> List[str]:
        ex = self.exercise_names.canonical(exercise)
        rows = self.fetch_all(
            "SELECT variant_name FROM exercise_variants WHERE exercise_name = ? ORDER BY variant_name;",
            (ex,),
        )
        return [r[0] for r in rows]


class SettingsRepository(BaseRepository):
    """Repository for general application settings synchronized with YAML."""

    def __init__(
        self, db_path: str = "workout.db", yaml_path: str = "settings.yaml"
    ) -> None:
        super().__init__(db_path)
        self._yaml = YamlConfig(yaml_path)
        self._sync_from_yaml()
        self._sync_to_yaml()

    def _raw_all_settings(self) -> dict:
        rows = self.fetch_all("SELECT key, value FROM settings ORDER BY key;")
        result: dict[str, float | str] = {}
        bool_keys = {
            "game_enabled",
            "ml_all_enabled",
            "ml_training_enabled",
            "ml_prediction_enabled",
            "ml_rpe_training_enabled",
            "ml_rpe_prediction_enabled",
            "ml_volume_training_enabled",
            "ml_volume_prediction_enabled",
            "ml_readiness_training_enabled",
            "ml_readiness_prediction_enabled",
            "ml_progress_training_enabled",
            "ml_progress_prediction_enabled",
            "ml_goal_training_enabled",
            "ml_goal_prediction_enabled",
            "ml_injury_training_enabled",
            "ml_injury_prediction_enabled",
            "experimental_models_enabled",
            "hide_preconfigured_equipment",
            "hide_preconfigured_exercises",
            "compact_mode",
            "auto_dark_mode",
            "large_font_mode",
            "show_onboarding",
            "show_help_tips",
            "auto_open_last_workout",
            "collapse_header",
            "email_weekly_enabled",
            "hide_completed_plans",
            "hide_completed_sets",
            "hide_nav_labels",
            "simple_mode",
            "hide_advanced_charts",
            "vertical_nav",
            "flex_metric_grid",
            "daily_reminders_enabled",
        }
        for k, v in rows:
            if k in bool_keys:
                result[k] = v in {"1", "1.0", "true", "True"}
                continue
            try:
                result[k] = float(v)
            except ValueError:
                result[k] = v
        return result

    def _sync_from_yaml(self) -> None:
        data = self._yaml.load()
        if not data:
            return
        validate_settings(data)
        with self._connection() as conn:
            bool_keys = {
                "game_enabled",
                "ml_all_enabled",
                "ml_training_enabled",
                "ml_prediction_enabled",
                "ml_rpe_training_enabled",
                "ml_rpe_prediction_enabled",
                "ml_volume_training_enabled",
                "ml_volume_prediction_enabled",
                "ml_readiness_training_enabled",
                "ml_readiness_prediction_enabled",
                "ml_progress_training_enabled",
                "ml_progress_prediction_enabled",
                "ml_goal_training_enabled",
                "ml_goal_prediction_enabled",
                "ml_injury_training_enabled",
                "ml_injury_prediction_enabled",
                "experimental_models_enabled",
                "hide_preconfigured_equipment",
                "hide_preconfigured_exercises",
                "compact_mode",
                "auto_dark_mode",
                "large_font_mode",
                "show_onboarding",
                "show_help_tips",
                "auto_open_last_workout",
                "collapse_header",
                "email_weekly_enabled",
            "hide_completed_plans",
            "hide_completed_sets",
            "hide_nav_labels",
            "simple_mode",
            "hide_advanced_charts",
            "vertical_nav",
            "flex_metric_grid",
            "daily_reminders_enabled",
        }
            for key, value in data.items():
                val = str(value)
                if key in bool_keys:
                    if val in {"1", "1.0", "true", "True"}:
                        val = "1"
                    else:
                        val = "0"
                conn.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value;",
                    (key, val),
                )

    def _sync_to_yaml(self) -> None:
        self._yaml.save(self._raw_all_settings())

    def get_float(self, key: str, default: float) -> float:
        self._sync_from_yaml()
        rows = self.fetch_all("SELECT value FROM settings WHERE key = ?;", (key,))
        return float(rows[0][0]) if rows else default

    def set_float(self, key: str, value: float) -> None:
        self.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value;",
            (key, str(value)),
        )
        self._sync_to_yaml()

    def get_text(self, key: str, default: str) -> str:
        self._sync_from_yaml()
        rows = self.fetch_all("SELECT value FROM settings WHERE key = ?;", (key,))
        return rows[0][0] if rows else default

    def get_int(self, key: str, default: int) -> int:
        try:
            return int(float(self.get_text(key, str(default))))
        except ValueError:
            return default

    def set_text(self, key: str, value: str) -> None:
        self.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value;",
            (key, value),
        )
        self._sync_to_yaml()

    def set_int(self, key: str, value: int) -> None:
        self.set_text(key, str(value))

    def get_list(self, key: str) -> list[str]:
        val = self.get_text(key, "")
        return [v for v in val.split(",") if v]

    def set_list(self, key: str, items: list[str]) -> None:
        self.set_text(key, ",".join(items))

    def get_bytes(self, key: str) -> bytes | None:
        val = self.get_text(key, "")
        if not val:
            return None
        import base64
        return base64.b64decode(val)

    def set_bytes(self, key: str, data: bytes) -> None:
        import base64
        b64 = base64.b64encode(data).decode("ascii")
        self.set_text(key, b64)

    def get_bool(self, key: str, default: bool) -> bool:
        return self.get_text(key, "1" if default else "0") in {
            "1",
            "true",
            "True",
            "1.0",
        }

    def set_bool(self, key: str, value: bool) -> None:
        self.set_text(key, "1" if value else "0")

    def all_settings(self) -> dict:
        self._sync_from_yaml()
        data = self._raw_all_settings()
        bool_keys = {
            "game_enabled",
            "ml_all_enabled",
            "ml_training_enabled",
            "ml_prediction_enabled",
            "ml_rpe_training_enabled",
            "ml_rpe_prediction_enabled",
            "ml_volume_training_enabled",
            "ml_volume_prediction_enabled",
            "ml_readiness_training_enabled",
            "ml_readiness_prediction_enabled",
            "ml_progress_training_enabled",
            "ml_progress_prediction_enabled",
            "ml_goal_training_enabled",
            "ml_goal_prediction_enabled",
            "ml_injury_training_enabled",
            "ml_injury_prediction_enabled",
            "experimental_models_enabled",
            "hide_preconfigured_equipment",
            "hide_preconfigured_exercises",
            "compact_mode",
            "auto_dark_mode",
            "large_font_mode",
            "show_onboarding",
            "show_help_tips",
            "auto_open_last_workout",
            "collapse_header",
            "email_weekly_enabled",
            "hide_completed_plans",
            "hide_completed_sets",
            "hide_nav_labels",
            "simple_mode",
            "vertical_nav",
            "flex_metric_grid",
            "daily_reminders_enabled",
        }
        for k in bool_keys:
            if k in data:
                data[k] = bool(data[k])
            else:
                data[k] = False
        if "timezone" not in data:
            data["timezone"] = "UTC"
        return data


class EquipmentTypeRepository(BaseRepository):
    """Repository for equipment type management."""

    def __init__(
        self,
        db_path: str = "workout.db",
        settings_repo: Optional[SettingsRepository] = None,
    ) -> None:
        super().__init__(db_path)
        self.settings = settings_repo

    def _hide_preconfigured(self) -> bool:
        if self.settings is None:
            return False
        return self.settings.get_bool("hide_preconfigured_equipment", False)

    def fetch_all(self) -> List[str]:
        # Equipment types should always be available regardless of the
        # ``hide_preconfigured_equipment`` setting. Filtering by ``is_custom``
        # would prevent selecting predefined types when adding new equipment.
        # Therefore we no longer apply the hide-preconfigured flag here.
        query = "SELECT name FROM equipment_types ORDER BY name;"
        rows = super().fetch_all(query)
        return [r[0] for r in rows]

    def exists(self, name: str) -> bool:
        rows = super().fetch_all(
            "SELECT id FROM equipment_types WHERE lower(name) = lower(?);",
            (name,),
        )
        return bool(rows)

    def add(self, name: str) -> int:
        if self.exists(name):
            raise ValueError("type exists")
        return self.execute(
            "INSERT INTO equipment_types (name, is_custom) VALUES (?, 1);",
            (name,),
        )

    def update(self, name: str, new_name: str) -> None:
        if self.exists(new_name):
            raise ValueError("type exists")
        rows = super().fetch_all(
            "SELECT is_custom FROM equipment_types WHERE name = ?;",
            (name,),
        )
        if not rows:
            raise ValueError("type not found")
        if rows[0][0] == 0:
            raise ValueError("cannot modify imported type")
        self.execute(
            "UPDATE equipment_types SET name = ? WHERE name = ?;",
            (new_name, name),
        )

    def remove(self, name: str) -> None:
        rows = super().fetch_all(
            "SELECT is_custom FROM equipment_types WHERE name = ?;",
            (name,),
        )
        if not rows:
            raise ValueError("type not found")
        if rows[0][0] == 0:
            raise ValueError("cannot delete imported type")
        self.execute("DELETE FROM equipment_types WHERE name = ?;", (name,))


class EquipmentRepository(BaseRepository):
    """Repository for equipment data."""

    def __init__(
        self,
        db_path: str = "workout.db",
        settings_repo: Optional[SettingsRepository] = None,
        type_repo: Optional[EquipmentTypeRepository] = None,
    ) -> None:
        super().__init__(db_path)
        self.muscles = MuscleRepository(db_path)
        self.settings = settings_repo
        self.types = type_repo or EquipmentTypeRepository(db_path, settings_repo)

    def _hide_preconfigured(self) -> bool:
        if self.settings is None:
            return False
        return self.settings.get_bool("hide_preconfigured_equipment", False)

    def upsert_many(self, records: Iterable[Tuple[str, str, str]]) -> None:
        for equipment_type, name, muscles in records:
            if not self.types.exists(equipment_type):
                self.types.execute(
                    "INSERT INTO equipment_types (name, is_custom) VALUES (?, 0);",
                    (equipment_type,),
                )
            self.muscles.ensure(muscles.split("|"))
            self.execute(
                "INSERT INTO equipment (equipment_type, name, muscles, is_custom) VALUES (?, ?, ?, 0) "
                "ON CONFLICT(name) DO UPDATE SET equipment_type=excluded.equipment_type, muscles=excluded.muscles;",
                (equipment_type, name, muscles),
            )

    def fetch_types(self) -> List[str]:
        return self.types.fetch_all()

    def fetch_names(
        self,
        equipment_type: Optional[str | List[str]] = None,
        prefix: Optional[str] = None,
        muscles: Optional[List[str]] = None,
    ) -> List[str]:
        query = "SELECT name FROM equipment WHERE 1=1"
        params: List[str] = []
        if isinstance(equipment_type, list) and equipment_type:
            placeholders = ",".join("?" for _ in equipment_type)
            query += f" AND equipment_type IN ({placeholders})"
            params.extend(equipment_type)
        elif equipment_type:
            query += " AND equipment_type = ?"
            params.append(equipment_type)
        if prefix:
            query += " AND name LIKE ?"
            params.append(f"{prefix}%")
        if muscles:
            for m in muscles:
                aliases = self.muscles.aliases(m)
                clause_parts = ["muscles LIKE ?" for _ in aliases]
                query += " AND (" + " OR ".join(clause_parts) + ")"
                params.extend([f"%{a}%" for a in aliases])
        if self._hide_preconfigured():
            query += " AND is_custom = 1"
        query += " ORDER BY name;"
        rows = self.fetch_all(query, tuple(params))
        return [r[0] for r in rows]

    def fetch_muscles(self, name: str) -> List[str]:
        rows = self.fetch_all("SELECT muscles FROM equipment WHERE name = ?;", (name,))
        if rows:
            result: List[str] = []
            for m in rows[0][0].split("|"):
                canon = self.muscles.canonical(m)
                if canon not in result:
                    result.append(canon)
            return result
        return []

    def fetch_detail(self, name: str) -> Optional[Tuple[str, List[str], int]]:
        rows = self.fetch_all(
            "SELECT equipment_type, muscles, is_custom FROM equipment WHERE name = ?;",
            (name,),
        )
        if rows:
            eq_type, muscles, is_custom = rows[0]
            musc_list = [self.muscles.canonical(m) for m in muscles.split("|") if m]
            return eq_type, musc_list, int(is_custom)
        return None

    def fetch_all_records(self) -> List[Tuple[str, str, str, int]]:
        query = (
            "SELECT name, equipment_type, muscles, is_custom FROM equipment WHERE 1=1"
        )
        if self._hide_preconfigured():
            query += " AND is_custom = 1"
        query += " ORDER BY name;"
        return self.fetch_all(query)

    def fetch_all_muscles(self) -> List[str]:
        query = "SELECT muscles FROM equipment"
        if self._hide_preconfigured():
            query += " WHERE is_custom = 1"
        query += ";"
        rows = self.fetch_all(query)
        muscles: Set[str] = set()
        for row in rows:
            for m in row[0].split("|"):
                muscles.add(self.muscles.canonical(m))
        return sorted(muscles)

    def fuzzy_search(self, query: str, limit: int = 5) -> List[str]:
        """Return equipment names closest to the query."""
        names = self.fetch_names()
        return difflib.get_close_matches(query, names, n=limit, cutoff=0.3)

    def add(self, equipment_type: str, name: str, muscles: List[str]) -> int:
        existing = self.fetch_all(
            "SELECT is_custom FROM equipment WHERE name = ?;",
            (name,),
        )
        if existing:
            raise ValueError("equipment exists")
        if not self.types.exists(equipment_type):
            raise ValueError("type not found")
        self.muscles.ensure(muscles)
        muscles_str = "|".join([self.muscles.canonical(m) for m in muscles])
        return self.execute(
            "INSERT INTO equipment (equipment_type, name, muscles, is_custom) VALUES (?, ?, ?, 1);",
            (equipment_type, name, muscles_str),
        )

    def update(
        self,
        name: str,
        equipment_type: str,
        muscles: List[str],
        new_name: Optional[str] = None,
    ) -> None:
        rows = self.fetch_all(
            "SELECT is_custom FROM equipment WHERE name = ?;",
            (name,),
        )
        if not rows:
            raise ValueError("equipment not found")
        if rows[0][0] == 0:
            raise ValueError("cannot modify imported equipment")
        if not self.types.exists(equipment_type):
            raise ValueError("type not found")
        target = new_name or name
        self.muscles.ensure(muscles)
        muscles_str = "|".join([self.muscles.canonical(m) for m in muscles])
        self.execute(
            "UPDATE equipment SET equipment_type = ?, name = ?, muscles = ? WHERE name = ?;",
            (equipment_type, target, muscles_str, name),
        )

    def remove(self, name: str) -> None:
        rows = self.fetch_all(
            "SELECT is_custom FROM equipment WHERE name = ?;",
            (name,),
        )
        if not rows:
            raise ValueError("equipment not found")
        if rows[0][0] == 0:
            raise ValueError("cannot delete imported equipment")
        self.execute("DELETE FROM equipment WHERE name = ?;", (name,))


class ExerciseCatalogRepository(BaseRepository):
    """Repository for exercise catalog data."""

    def __init__(
        self,
        db_path: str = "workout.db",
        settings_repo: Optional[SettingsRepository] = None,
    ) -> None:
        super().__init__(db_path)
        self.muscles = MuscleRepository(db_path)
        self.exercise_names = ExerciseNameRepository(db_path)
        self.settings = settings_repo

    def _hide_preconfigured(self) -> bool:
        if self.settings is None:
            return False
        return self.settings.get_bool("hide_preconfigured_exercises", False)

    def fetch_muscle_groups(self) -> List[str]:
        query = "SELECT DISTINCT muscle_group FROM exercise_catalog WHERE 1=1"
        if self._hide_preconfigured():
            query += " AND is_custom = 1"
        query += " ORDER BY muscle_group;"
        rows = self.fetch_all(query)
        return [r[0] for r in rows]

    def fetch_names(
        self,
        muscle_groups: Optional[List[str]] = None,
        muscles: Optional[List[str]] = None,
        equipment: Optional[str] = None,
        prefix: Optional[str] = None,
        no_equipment: bool = False,
        sort_by: str = "name",
    ) -> List[str]:
        query = "SELECT name FROM exercise_catalog WHERE 1=1"
        params: List[str] = []
        if muscle_groups:
            placeholders = ",".join(["?" for _ in muscle_groups])
            query += f" AND muscle_group IN ({placeholders})"
            params.extend(muscle_groups)
        if equipment:
            query += " AND equipment_names LIKE ?"
            params.append(f"%{equipment}%")
        if no_equipment:
            query += " AND (equipment_names IS NULL OR equipment_names = '')"
        if prefix:
            query += " AND name LIKE ?"
            params.append(f"{prefix}%")
        if muscles:
            muscle_clauses = []
            for muscle in muscles:
                aliases = self.muscles.aliases(muscle)
                cols = [
                    "primary_muscle",
                    "secondary_muscle",
                    "tertiary_muscle",
                    "other_muscles",
                ]
                alias_clauses = []
                for alias in aliases:
                    pattern = f"%{alias}%"
                    alias_clauses.extend([f"{c} LIKE ?" for c in cols])
                    params.extend([pattern] * len(cols))
                muscle_clauses.append("(" + " OR ".join(alias_clauses) + ")")
            query += " AND (" + " OR ".join(muscle_clauses) + ")"
        if self._hide_preconfigured():
            query += " AND is_custom = 1"
        allowed = {"name", "muscle_group"}
        if sort_by not in allowed:
            sort_by = "name"
        query += f" ORDER BY {sort_by};"
        rows = self.fetch_all(query, tuple(params))
        result: List[str] = []
        for (name,) in rows:
            result.extend(self.exercise_names.aliases(name))
        return sorted(dict.fromkeys(result))

    def fetch_detail(
        self, name: str
    ) -> Optional[Tuple[str, str, str, str, str, str, str, str]]:
        canonical = self.exercise_names.canonical(name)
        rows = self.fetch_all(
            "SELECT muscle_group, variants, equipment_names, primary_muscle, secondary_muscle, tertiary_muscle, other_muscles, video_url, is_custom FROM exercise_catalog WHERE name = ?;",
            (canonical,),
        )
        if rows:
            (
                group,
                variants,
                equipment_names,
                primary,
                secondary,
                tertiary,
                other,
                video,
                is_custom,
            ) = rows[0]

            def canon_list(text: str) -> str:
                items = [self.muscles.canonical(m) for m in text.split("|") if m]
                return "|".join(dict.fromkeys(items))

            return (
                group,
                variants,
                equipment_names,
                canon_list(primary),
                canon_list(secondary),
                canon_list(tertiary),
                canon_list(other),
                video,
                is_custom,
            )
        return None

    def fetch_all_records(
        self, custom_only: bool = False
    ) -> List[Tuple[str, str, str, str, str, str, str, str, int]]:
        query = (
            "SELECT name, muscle_group, variants, equipment_names, primary_muscle, "
            "secondary_muscle, tertiary_muscle, other_muscles, video_url, is_custom FROM "
            "exercise_catalog WHERE 1=1"
        )
        if custom_only or self._hide_preconfigured():
            query += " AND is_custom = 1"
        query += " ORDER BY name;"
        rows = self.fetch_all(query)
        result = []
        for (
            name,
            group,
            variants,
            equipment_names,
            primary,
            secondary,
            tertiary,
            other,
            video,
            is_custom,
        ) in rows:

            def canon(text: str) -> str:
                items = [self.muscles.canonical(m) for m in text.split("|") if m]
                return "|".join(dict.fromkeys(items))

            result.append(
                (
                    name,
                    group,
                    variants,
                    equipment_names,
                    canon(primary),
                    canon(secondary),
                canon(tertiary),
                canon(other),
                video,
                is_custom,
            )
        )
        return result

    def fetch_all_muscles(self) -> List[str]:
        query = (
            "SELECT primary_muscle, secondary_muscle, tertiary_muscle, other_muscles FROM exercise_catalog"
        )
        if self._hide_preconfigured():
            query += " WHERE is_custom = 1"
        query += ";"
        rows = self.fetch_all(query)
        muscles: Set[str] = set()
        for pm, sm, tm, om in rows:
            for field in [pm, sm, tm, om]:
                if field:
                    for m in field.split("|"):
                        if m:
                            muscles.add(self.muscles.canonical(m))
        return sorted(muscles)

    def add(
        self,
        muscle_group: str,
        name: str,
        variants: str,
        equipment_names: str,
        primary_muscle: str,
        secondary_muscle: str,
        tertiary_muscle: str,
        other_muscles: str,
        video_url: str = "",
    ) -> int:
        existing = self.fetch_all(
            "SELECT is_custom FROM exercise_catalog WHERE name = ?;",
            (name,),
        )
        if existing:
            raise ValueError("exercise exists")
        self.exercise_names.ensure([name])
        muscs = (
            [primary_muscle]
            + secondary_muscle.split("|")
            + tertiary_muscle.split("|")
            + other_muscles.split("|")
        )
        self.muscles.ensure([m for m in muscs if m])
        primary_muscle = self.muscles.canonical(primary_muscle)
        secondary_muscle = "|".join(
            [self.muscles.canonical(m) for m in secondary_muscle.split("|") if m]
        )
        tertiary_muscle = "|".join(
            [self.muscles.canonical(m) for m in tertiary_muscle.split("|") if m]
        )
        other_muscles = "|".join(
            [self.muscles.canonical(m) for m in other_muscles.split("|") if m]
        )
        return self.execute(
            "INSERT INTO exercise_catalog (muscle_group, name, variants, equipment_names, primary_muscle, secondary_muscle, tertiary_muscle, other_muscles, video_url, is_custom) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1);",
            (
                muscle_group,
                name,
                variants,
                equipment_names,
                primary_muscle,
                secondary_muscle,
                tertiary_muscle,
                other_muscles,
                video_url,
            ),
        )

    def update(
        self,
        name: str,
        muscle_group: str,
        variants: str,
        equipment_names: str,
        primary_muscle: str,
        secondary_muscle: str,
        tertiary_muscle: str,
        other_muscles: str,
        video_url: str = "",
        new_name: Optional[str] = None,
    ) -> None:
        rows = self.fetch_all(
            "SELECT is_custom FROM exercise_catalog WHERE name = ?;",
            (name,),
        )
        if not rows:
            raise ValueError("exercise not found")
        if rows[0][0] == 0:
            raise ValueError("cannot modify imported exercise")
        target = new_name or name
        self.exercise_names.ensure([target])
        muscs = (
            [primary_muscle]
            + secondary_muscle.split("|")
            + tertiary_muscle.split("|")
            + other_muscles.split("|")
        )
        self.muscles.ensure([m for m in muscs if m])
        primary_muscle = self.muscles.canonical(primary_muscle)
        secondary_muscle = "|".join(
            [self.muscles.canonical(m) for m in secondary_muscle.split("|") if m]
        )
        tertiary_muscle = "|".join(
            [self.muscles.canonical(m) for m in tertiary_muscle.split("|") if m]
        )
        other_muscles = "|".join(
            [self.muscles.canonical(m) for m in other_muscles.split("|") if m]
        )
        self.execute(
            "UPDATE exercise_catalog SET muscle_group = ?, name = ?, variants = ?, equipment_names = ?, primary_muscle = ?, secondary_muscle = ?, tertiary_muscle = ?, other_muscles = ?, video_url = ? WHERE name = ?;",
            (
                muscle_group,
                target,
                variants,
                equipment_names,
                primary_muscle,
                secondary_muscle,
                tertiary_muscle,
                other_muscles,
                video_url,
                name,
            ),
        )

    def remove(self, name: str) -> None:
        rows = self.fetch_all(
            "SELECT is_custom FROM exercise_catalog WHERE name = ?;",
            (name,),
        )
        if not rows:
            raise ValueError("exercise not found")
        if rows[0][0] == 0:
            raise ValueError("cannot delete imported exercise")
        self.execute("DELETE FROM exercise_catalog WHERE name = ?;", (name,))


class PyramidTestRepository(BaseRepository):
    """Repository for pyramid tests."""

    def create(
        self,
        date: str,
        exercise_name: str = "Unknown",
        equipment_name: str | None = None,
        starting_weight: float | None = None,
        failed_weight: float | None = None,
        max_achieved: float | None = None,
        test_duration_minutes: int | None = None,
        rest_between_attempts: str | None = None,
        rpe_per_attempt: str | None = None,
        time_of_day: str | None = None,
        sleep_hours: float | None = None,
        stress_level: int | None = None,
        nutrition_quality: int | None = None,
    ) -> int:
        return self.execute(
            """
            INSERT INTO pyramid_tests (
                exercise_name,
                date,
                equipment_name,
                starting_weight,
                failed_weight,
                max_achieved,
                test_duration_minutes,
                rest_between_attempts,
                rpe_per_attempt,
                time_of_day,
                sleep_hours,
                stress_level,
                nutrition_quality
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                exercise_name,
                date,
                equipment_name,
                starting_weight,
                failed_weight,
                max_achieved,
                test_duration_minutes,
                rest_between_attempts,
                rpe_per_attempt,
                time_of_day,
                sleep_hours,
                stress_level,
                nutrition_quality,
            ),
        )

    def fetch_all(self) -> List[Tuple[int, str]]:
        return super().fetch_all("SELECT id, date FROM pyramid_tests ORDER BY id DESC;")

    def fetch_all_full(self) -> List[Tuple]:
        return super().fetch_all(
            "SELECT id, exercise_name, date, equipment_name, starting_weight, failed_weight, max_achieved, test_duration_minutes, rest_between_attempts, rpe_per_attempt, time_of_day, sleep_hours, stress_level, nutrition_quality FROM pyramid_tests ORDER BY id DESC;"
        )

    def fetch_all_with_weights(
        self, entries: "PyramidEntryRepository"
    ) -> List[Tuple[int, str, List[float]]]:
        tests = self.fetch_all()
        result = []
        for tid, date in tests:
            weights = entries.fetch_for_test(tid)
            result.append((tid, date, weights))
        return result

    def fetch_full_with_weights(self, entries: "PyramidEntryRepository") -> List[Tuple]:
        tests = self.fetch_all_full()
        result = []
        for row in tests:
            tid = row[0]
            weights = entries.fetch_for_test(tid)
            result.append(tuple(row) + (weights,))
        return result


class PyramidEntryRepository(BaseRepository):
    """Repository for pyramid test entries."""

    def add(self, test_id: int, weight: float) -> int:
        return self.execute(
            "INSERT INTO pyramid_entries (pyramid_test_id, weight) VALUES (?, ?);",
            (test_id, weight),
        )

    def fetch_for_test(self, test_id: int) -> List[float]:
        rows = self.fetch_all(
            "SELECT weight FROM pyramid_entries WHERE pyramid_test_id = ? ORDER BY id;",
            (test_id,),
        )
        return [float(r[0]) for r in rows]


class GamificationRepository(BaseRepository):
    """Repository for gamification points."""

    def add(self, workout_id: int, points: float) -> int:
        return self.execute(
            "INSERT INTO gamification_points (workout_id, points) VALUES (?, ?);",
            (workout_id, points),
        )

    def fetch_for_workout(self, workout_id: int) -> List[float]:
        rows = self.fetch_all(
            "SELECT points FROM gamification_points WHERE workout_id = ? ORDER BY id;",
            (workout_id,),
        )
        return [float(r[0]) for r in rows]

    def total_points(self) -> float:
        rows = self.fetch_all("SELECT SUM(points) FROM gamification_points;")
        return float(rows[0][0] or 0.0)

    def workout_totals(self) -> List[Tuple[int, float]]:
        rows = self.fetch_all(
            "SELECT workout_id, SUM(points) FROM gamification_points "
            "GROUP BY workout_id ORDER BY workout_id;"
        )
        return [(int(wid), float(pts or 0.0)) for wid, pts in rows]


class ChallengeRepository(BaseRepository):
    """Repository for tracking challenges."""

    def add(self, name: str, target: int) -> int:
        return self.execute(
            "INSERT INTO challenges (name, target) VALUES (?, ?);",
            (name, target),
        )

    def update_progress(self, challenge_id: int, progress: int) -> None:
        rows = super().fetch_all(
            "SELECT id FROM challenges WHERE id = ?;",
            (challenge_id,),
        )
        if not rows:
            raise ValueError("challenge not found")
        self.execute(
            "UPDATE challenges SET progress = ? WHERE id = ?;",
            (progress, challenge_id),
        )

    def set_completed(self, challenge_id: int, completed: bool = True) -> None:
        self.execute(
            "UPDATE challenges SET completed = ? WHERE id = ?;",
            (1 if completed else 0, challenge_id),
        )

    def fetch_all(self) -> list[tuple[int, str, int, int, int]]:
        rows = super().fetch_all(
            "SELECT id, name, target, progress, completed FROM challenges ORDER BY id;"
        )
        return [
            (int(cid), n, int(t), int(p), int(c))
            for cid, n, t, p, c in rows
        ]


class MLModelRepository(BaseRepository):
    """Repository for storing Torch model states."""

    def save(self, name: str, state: bytes) -> None:
        self.execute(
            "INSERT INTO ml_models (name, state) VALUES (?, ?) "
            "ON CONFLICT(name) DO UPDATE SET state=excluded.state;",
            (name, state),
        )

    def load(self, name: str) -> bytes | None:
        rows = self.fetch_all(
            "SELECT state FROM ml_models WHERE name = ?;",
            (name,),
        )
        return rows[0][0] if rows else None


class MLLogRepository(BaseRepository):
    """Repository for logging model predictions and confidence."""

    def add(self, name: str, prediction: float, confidence: float) -> int:
        return self.execute(
            "INSERT INTO ml_logs (name, timestamp, prediction, confidence) VALUES (?, ?, ?, ?);",
            (name, datetime.datetime.now().isoformat(), prediction, confidence),
        )

    def fetch(self, name: str) -> list[tuple[str, float, float]]:
        return self.fetch_all(
            "SELECT timestamp, prediction, confidence FROM ml_logs WHERE name = ? ORDER BY id;",
            (name,),
        )

    def fetch_range(
        self,
        name: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[tuple[str, float, float]]:
        """Return logs for ``name`` optionally filtered by ISO date range."""
        query = (
            "SELECT timestamp, prediction, confidence FROM ml_logs " "WHERE name = ?"
        )
        params: list[str] = [name]
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)
        query += " ORDER BY id;"
        rows = self.fetch_all(query, tuple(params))
        return [(r[0], float(r[1]), float(r[2])) for r in rows]


class BodyWeightRepository(BaseRepository):
    """Repository for body weight logs."""

    def log(self, date: str, weight: float) -> int:
        if weight <= 0:
            raise ValueError("weight must be positive")
        return self.execute(
            "INSERT INTO body_weight_logs (date, weight) VALUES (?, ?);",
            (date, weight),
        )

    def fetch_history(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> list[tuple[int, str, float]]:
        query = "SELECT id, date, weight FROM body_weight_logs WHERE 1=1"
        params: list[str] = []
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        query += " ORDER BY date;"
        rows = self.fetch_all(query, tuple(params))
        return [(int(r[0]), r[1], float(r[2])) for r in rows]

    def update(self, entry_id: int, date: str, weight: float) -> None:
        if weight <= 0:
            raise ValueError("weight must be positive")
        rows = self.fetch_all(
            "SELECT id FROM body_weight_logs WHERE id = ?;",
            (entry_id,),
        )
        if not rows:
            raise ValueError("log not found")
        self.execute(
            "UPDATE body_weight_logs SET date = ?, weight = ? WHERE id = ?;",
            (date, weight, entry_id),
        )

    def delete(self, entry_id: int) -> None:
        rows = self.fetch_all(
            "SELECT id FROM body_weight_logs WHERE id = ?;",
            (entry_id,),
        )
        if not rows:
            raise ValueError("log not found")
        self.execute("DELETE FROM body_weight_logs WHERE id = ?;", (entry_id,))

    def fetch_latest_weight(self) -> float | None:
        """Return the most recent logged body weight if available."""
        row = self.fetch_all(
            "SELECT weight FROM body_weight_logs ORDER BY date DESC LIMIT 1;"
        )
        if row:
            return float(row[0][0])
        return None


class WellnessRepository(BaseRepository):
    """Repository for daily wellness logs."""

    def log(
        self,
        date: str,
        calories: float | None = None,
        sleep_hours: float | None = None,
        sleep_quality: float | None = None,
        stress_level: int | None = None,
    ) -> int:
        if (
            calories is None
            and sleep_hours is None
            and sleep_quality is None
            and stress_level is None
        ):
            raise ValueError("at least one value required")
        return self.execute(
            "INSERT INTO wellness_logs (date, calories, sleep_hours, sleep_quality, stress_level) VALUES (?, ?, ?, ?, ?);",
            (date, calories, sleep_hours, sleep_quality, stress_level),
        )

    def fetch_history(
        self, start_date: str | None = None, end_date: str | None = None
    ) -> list[tuple[int, str, float | None, float | None, float | None, int | None]]:
        query = "SELECT id, date, calories, sleep_hours, sleep_quality, stress_level FROM wellness_logs WHERE 1=1"
        params: list[str] = []
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        query += " ORDER BY date;"
        rows = self.fetch_all(query, tuple(params))
        return [
            (
                int(r[0]),
                r[1],
                float(r[2]) if r[2] is not None else None,
                float(r[3]) if r[3] is not None else None,
                float(r[4]) if r[4] is not None else None,
                int(r[5]) if r[5] is not None else None,
            )
            for r in rows
        ]

    def update(
        self,
        entry_id: int,
        date: str,
        calories: float | None = None,
        sleep_hours: float | None = None,
        sleep_quality: float | None = None,
        stress_level: int | None = None,
    ) -> None:
        rows = self.fetch_all(
            "SELECT id FROM wellness_logs WHERE id = ?;",
            (entry_id,),
        )
        if not rows:
            raise ValueError("log not found")
        self.execute(
            "UPDATE wellness_logs SET date = ?, calories = ?, sleep_hours = ?, sleep_quality = ?, stress_level = ? WHERE id = ?;",
            (date, calories, sleep_hours, sleep_quality, stress_level, entry_id),
        )

    def delete(self, entry_id: int) -> None:
        rows = self.fetch_all(
            "SELECT id FROM wellness_logs WHERE id = ?;",
            (entry_id,),
        )
        if not rows:
            raise ValueError("log not found")
        self.execute("DELETE FROM wellness_logs WHERE id = ?;", (entry_id,))


class HeartRateRepository(BaseRepository):
    """Repository for logging heart rate during workouts."""

    def log(self, workout_id: int, timestamp: str, heart_rate: int) -> int:
        return self.execute(
            "INSERT INTO heart_rate_logs (workout_id, timestamp, heart_rate) VALUES (?, ?, ?);",
            (workout_id, timestamp, heart_rate),
        )

    def bulk_log(self, workout_id: int, entries: list[tuple[str, int]]) -> list[int]:
        """Insert multiple heart rate entries and return their ids."""
        ids: list[int] = []
        for ts, hr in entries:
            ids.append(self.log(workout_id, ts, hr))
        return ids

    def fetch_for_workout(self, workout_id: int) -> list[tuple[int, str, int]]:
        rows = self.fetch_all(
            "SELECT id, timestamp, heart_rate FROM heart_rate_logs WHERE workout_id = ? ORDER BY timestamp;",
            (workout_id,),
        )
        return [(int(r[0]), r[1], int(r[2])) for r in rows]

    def fetch_range(self, start_date: str | None = None, end_date: str | None = None) -> list[tuple[int, int, str, int]]:
        query = (
            "SELECT hr.id, hr.workout_id, hr.timestamp, hr.heart_rate FROM heart_rate_logs hr JOIN workouts w ON hr.workout_id = w.id WHERE 1=1"
        )
        params: list[str] = []
        if start_date:
            query += " AND w.date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND w.date <= ?"
            params.append(end_date)
        query += " ORDER BY timestamp;"
        rows = self.fetch_all(query, tuple(params))
        return [(int(r[0]), int(r[1]), r[2], int(r[3])) for r in rows]

    def update(self, entry_id: int, timestamp: str, heart_rate: int) -> None:
        rows = self.fetch_all(
            "SELECT id FROM heart_rate_logs WHERE id = ?;",
            (entry_id,),
        )
        if not rows:
            raise ValueError("log not found")
        self.execute(
            "UPDATE heart_rate_logs SET timestamp = ?, heart_rate = ? WHERE id = ?;",
            (timestamp, heart_rate, entry_id),
        )

    def delete(self, entry_id: int) -> None:
        rows = self.fetch_all(
            "SELECT id FROM heart_rate_logs WHERE id = ?;",
            (entry_id,),
        )
        if not rows:
            raise ValueError("log not found")
        self.execute("DELETE FROM heart_rate_logs WHERE id = ?;", (entry_id,))


class StepCountRepository(BaseRepository):
    """Repository for logging step counts during cardio workouts."""

    def log(self, workout_id: int, timestamp: str, steps: int) -> int:
        return self.execute(
            "INSERT INTO step_count_logs (workout_id, timestamp, steps) VALUES (?, ?, ?);",
            (workout_id, timestamp, steps),
        )

    def bulk_log(self, workout_id: int, entries: list[tuple[str, int]]) -> list[int]:
        """Insert multiple step count entries and return their ids."""
        ids: list[int] = []
        for ts, st in entries:
            ids.append(self.log(workout_id, ts, st))
        return ids

    def fetch_for_workout(self, workout_id: int) -> list[tuple[int, str, int]]:
        rows = self.fetch_all(
            "SELECT id, timestamp, steps FROM step_count_logs WHERE workout_id = ? ORDER BY timestamp;",
            (workout_id,),
        )
        return [(int(r[0]), r[1], int(r[2])) for r in rows]

    def fetch_range(self, start_date: str | None = None, end_date: str | None = None) -> list[tuple[int, int, str, int]]:
        query = (
            "SELECT sc.id, sc.workout_id, sc.timestamp, sc.steps FROM step_count_logs sc JOIN workouts w ON sc.workout_id = w.id WHERE 1=1"
        )
        params: list[str] = []
        if start_date:
            query += " AND w.date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND w.date <= ?"
            params.append(end_date)
        query += " ORDER BY timestamp;"
        rows = self.fetch_all(query, tuple(params))
        return [(int(r[0]), int(r[1]), r[2], int(r[3])) for r in rows]

    def update(self, entry_id: int, timestamp: str, steps: int) -> None:
        rows = self.fetch_all(
            "SELECT id FROM step_count_logs WHERE id = ?;",
            (entry_id,),
        )
        if not rows:
            raise ValueError("log not found")
        self.execute(
            "UPDATE step_count_logs SET timestamp = ?, steps = ? WHERE id = ?;",
            (timestamp, steps, entry_id),
        )

    def delete(self, entry_id: int) -> None:
        rows = self.fetch_all(
            "SELECT id FROM step_count_logs WHERE id = ?;",
            (entry_id,),
        )
        if not rows:
            raise ValueError("log not found")
        self.execute("DELETE FROM step_count_logs WHERE id = ?;", (entry_id,))


class ExerciseImageRepository(BaseRepository):
    """Repository for storing exercise demonstration images."""

    def __init__(self, db_path: str = "workout.db") -> None:
        super().__init__(db_path)
        self.exercise_names = ExerciseNameRepository(db_path)

    def set(self, exercise_name: str, path: str, thumbnail_path: str | None = None) -> None:
        self.exercise_names.ensure([exercise_name])
        self.execute(
            "INSERT INTO exercise_images (exercise_name, path, thumbnail_path) VALUES (?, ?, ?) "
            "ON CONFLICT(exercise_name) DO UPDATE SET path=excluded.path, thumbnail_path=excluded.thumbnail_path;",
            (exercise_name, path, thumbnail_path),
        )

    def fetch(self, exercise_name: str) -> tuple[str, str | None] | None:
        rows = self.fetch_all(
            "SELECT path, thumbnail_path FROM exercise_images WHERE exercise_name = ?;",
            (exercise_name,),
        )
        return (rows[0][0], rows[0][1]) if rows else None

    def delete(self, exercise_name: str) -> None:
        self.execute(
            "DELETE FROM exercise_images WHERE exercise_name = ?;",
            (exercise_name,),
        )


class FavoriteExerciseRepository(BaseRepository):
    """Repository for managing favorite exercises."""

    def add(self, name: str) -> None:
        self.execute(
            "INSERT OR IGNORE INTO favorite_exercises (name) VALUES (?);",
            (name,),
        )

    def remove(self, name: str) -> None:
        self.execute(
            "DELETE FROM favorite_exercises WHERE name = ?;",
            (name,),
        )

    def fetch_all(self) -> list[str]:
        rows = super().fetch_all("SELECT name FROM favorite_exercises ORDER BY name;")
        return [r[0] for r in rows]


class FavoriteTemplateRepository(BaseRepository):
    """Repository for managing favorite workout templates."""

    def add(self, template_id: int) -> None:
        self.execute(
            "INSERT OR IGNORE INTO favorite_templates (template_id) VALUES (?);",
            (template_id,),
        )

    def remove(self, template_id: int) -> None:
        self.execute(
            "DELETE FROM favorite_templates WHERE template_id = ?;",
            (template_id,),
        )

    def fetch_all(self) -> list[int]:
        rows = super().fetch_all(
            "SELECT template_id FROM favorite_templates ORDER BY template_id;"
        )
        return [int(r[0]) for r in rows]


class FavoriteWorkoutRepository(BaseRepository):
    """Repository for managing favorite workouts."""

    def add(self, workout_id: int) -> None:
        self.execute(
            "INSERT OR IGNORE INTO favorite_workouts (workout_id) VALUES (?);",
            (workout_id,),
        )

    def remove(self, workout_id: int) -> None:
        self.execute(
            "DELETE FROM favorite_workouts WHERE workout_id = ?;",
            (workout_id,),
        )

    def fetch_all(self) -> list[int]:
        rows = super().fetch_all(
            "SELECT workout_id FROM favorite_workouts ORDER BY workout_id;"
        )
        return [int(r[0]) for r in rows]


class DefaultEquipmentRepository(BaseRepository):
    """Repository managing default equipment per exercise."""

    def __init__(self, db_path: str = "workout.db", names: Optional[ExerciseNameRepository] = None) -> None:
        super().__init__(db_path)
        self.names = names or ExerciseNameRepository(db_path)

    def set(self, exercise_name: str, equipment_name: str) -> None:
        canonical = self.names.canonical(exercise_name)
        self.execute(
            "INSERT INTO default_equipment (exercise_name, equipment_name) VALUES (?, ?) "
            "ON CONFLICT(exercise_name) DO UPDATE SET equipment_name=excluded.equipment_name;",
            (canonical, equipment_name),
        )

    def fetch(self, exercise_name: str) -> Optional[str]:
        canonical = self.names.canonical(exercise_name)
        rows = super().fetch_all(
            "SELECT equipment_name FROM default_equipment WHERE exercise_name = ?;",
            (canonical,),
        )
        return rows[0][0] if rows else None

    def delete(self, exercise_name: str) -> None:
        canonical = self.names.canonical(exercise_name)
        self.execute("DELETE FROM default_equipment WHERE exercise_name = ?;", (canonical,))

    def fetch_all(self) -> list[tuple[str, str]]:
        rows = super().fetch_all(
            "SELECT exercise_name, equipment_name FROM default_equipment ORDER BY exercise_name;"
        )
        return [(r[0], r[1]) for r in rows]


class ReactionRepository(BaseRepository):
    """Repository for storing emoji reactions to workouts."""

    def react(self, workout_id: int, emoji: str) -> None:
        """Add an emoji reaction for the given workout."""
        row = super().fetch_all(
            "SELECT count FROM workout_reactions WHERE workout_id = ? AND emoji = ?;",
            (workout_id, emoji),
        )
        if row:
            new_count = int(row[0][0]) + 1
            self.execute(
                "UPDATE workout_reactions SET count = ? WHERE workout_id = ? AND emoji = ?;",
                (new_count, workout_id, emoji),
            )
        else:
            self.execute(
                "INSERT INTO workout_reactions (workout_id, emoji, count) VALUES (?, ?, 1);",
                (workout_id, emoji),
            )

    def list_for_workout(self, workout_id: int) -> list[tuple[str, int]]:
        """Return all reactions for ``workout_id`` sorted by emoji."""
        rows = super().fetch_all(
            "SELECT emoji, count FROM workout_reactions WHERE workout_id = ? ORDER BY emoji;",
            (workout_id,),
        )
        return [(r[0], int(r[1])) for r in rows]


class AsyncReactionRepository(AsyncBaseRepository):
    """Async repository for storing emoji reactions."""

    async def react(self, workout_id: int, emoji: str) -> None:
        row = await super().fetch_all(
            "SELECT count FROM workout_reactions WHERE workout_id = ? AND emoji = ?;",
            (workout_id, emoji),
        )
        if row:
            new_count = int(row[0][0]) + 1
            await self.execute(
                "UPDATE workout_reactions SET count = ? WHERE workout_id = ? AND emoji = ?;",
                (new_count, workout_id, emoji),
            )
        else:
            await self.execute(
                "INSERT INTO workout_reactions (workout_id, emoji, count) VALUES (?, ?, 1);",
                (workout_id, emoji),
            )

    async def list_for_workout(self, workout_id: int) -> list[tuple[str, int]]:
        rows = await super().fetch_all(
            "SELECT emoji, count FROM workout_reactions WHERE workout_id = ? ORDER BY emoji;",
            (workout_id,),
        )
        return [(r[0], int(r[1])) for r in rows]


class APIKeyRepository(BaseRepository):
    """Repository for managing third-party API keys."""

    def add(self, name: str, key: str) -> int:
        return self.execute(
            "INSERT INTO api_keys (name, api_key) VALUES (?, ?);",
            (name, key),
        )

    def fetch_all(self) -> list[tuple[int, str, str]]:
        rows = super().fetch_all(
            "SELECT id, name, api_key FROM api_keys ORDER BY id;"
        )
        return [(int(r[0]), r[1], r[2]) for r in rows]

    def delete(self, key_id: int) -> None:
        self.execute("DELETE FROM api_keys WHERE id = ?;", (key_id,))


class TemplateWorkoutRepository(BaseRepository):
    """Repository for workout templates."""

    def create(
        self, name: str, training_type: str = "strength", color: str = "#ffffff"
    ) -> int:
        rows = super().fetch_all(
            "SELECT COALESCE(MAX(position), 0) + 1 FROM workout_templates;"
        )
        position = int(rows[0][0]) if rows else 1
        return self.execute(
            "INSERT INTO workout_templates (name, training_type, position, color) VALUES (?, ?, ?, ?);",
            (name, training_type, position, color),
        )

    def fetch_all(self) -> list[tuple[int, str, str, str]]:
        return super().fetch_all(
            "SELECT id, name, training_type, color FROM workout_templates ORDER BY position;"
        )

    def fetch_detail(self, template_id: int) -> tuple[int, str, str, str]:
        rows = super().fetch_all(
            "SELECT id, name, training_type, color FROM workout_templates WHERE id = ?;",
            (template_id,),
        )
        if not rows:
            raise ValueError("template not found")
        return rows[0]

    def update(
        self,
        template_id: int,
        name: str | None,
        training_type: str | None,
        color: str | None = None,
    ) -> None:
        rows = super().fetch_all(
            "SELECT id FROM workout_templates WHERE id = ?;",
            (template_id,),
        )
        if not rows:
            raise ValueError("template not found")
        if name is not None:
            self.execute(
                "UPDATE workout_templates SET name = ? WHERE id = ?;",
                (name, template_id),
            )
        if training_type is not None:
            self.execute(
                "UPDATE workout_templates SET training_type = ? WHERE id = ?;",
                (training_type, template_id),
            )
        if color is not None:
            self.execute(
                "UPDATE workout_templates SET color = ? WHERE id = ?;",
                (color, template_id),
            )

    def delete(self, template_id: int) -> None:
        rows = super().fetch_all(
            "SELECT id FROM workout_templates WHERE id = ?;",
            (template_id,),
        )
        if not rows:
            raise ValueError("template not found")
        self.execute("DELETE FROM workout_templates WHERE id = ?;", (template_id,))

    def reorder(self, order: list[int]) -> None:
        existing = [
            row[0]
            for row in super().fetch_all(
                "SELECT id FROM workout_templates ORDER BY position;"
            )
        ]
        if set(order) != set(existing) or len(order) != len(existing):
            raise ValueError("invalid order")
        for pos, tid in enumerate(order, start=1):
            self.execute(
                "UPDATE workout_templates SET position = ? WHERE id = ?;",
                (pos, tid),
            )

    def update_last_used(self, template_id: int) -> None:
        self.execute(
            "UPDATE workout_templates SET last_used = ? WHERE id = ?;",
            (datetime.date.today().isoformat(), template_id),
        )

    def fetch_recent(self, limit: int = 5) -> list[tuple[int, str]]:
        rows = super().fetch_all(
            "SELECT id, name FROM workout_templates WHERE last_used IS NOT NULL ORDER BY last_used DESC LIMIT ?;",
            (limit,),
        )
        return [(r[0], r[1]) for r in rows]

    def clone(self, template_id: int, new_name: str) -> int:
        tid, _name, t_type, color = self.fetch_detail(template_id)
        new_id = self.create(new_name, t_type, color)
        exercises = TemplateExerciseRepository(self._db_path)
        sets = TemplateSetRepository(self._db_path)
        for ex_id, name, eq in exercises.fetch_for_template(tid):
            new_ex_id = exercises.add(new_id, name, eq)
            for _sid, reps, weight, rpe in sets.fetch_for_exercise(ex_id):
                sets.add(new_ex_id, reps, weight, rpe)
        return new_id


class TemplateExerciseRepository(BaseRepository):
    """Repository for exercises belonging to templates."""

    def add(self, template_id: int, name: str, equipment_name: str | None) -> int:
        return self.execute(
            "INSERT INTO template_exercises (template_id, name, equipment_name) VALUES (?, ?, ?);",
            (template_id, name, equipment_name),
        )

    def remove(self, exercise_id: int) -> None:
        self.execute("DELETE FROM template_exercises WHERE id = ?;", (exercise_id,))

    def fetch_for_template(self, template_id: int) -> list[tuple[int, str, str | None]]:
        return self.fetch_all(
            "SELECT id, name, equipment_name FROM template_exercises WHERE template_id = ?;",
            (template_id,),
        )


class TemplateSetRepository(BaseRepository):
    """Repository for template sets."""

    def add(self, exercise_id: int, reps: int, weight: float, rpe: int) -> int:
        return self.execute(
            "INSERT INTO template_sets (template_exercise_id, reps, weight, rpe) VALUES (?, ?, ?, ?);",
            (exercise_id, reps, weight, rpe),
        )

    def fetch_for_exercise(self, exercise_id: int) -> list[tuple[int, int, float, int]]:
        return self.fetch_all(
            "SELECT id, reps, weight, rpe FROM template_sets WHERE template_exercise_id = ?;",
            (exercise_id,),
        )


class TagRepository(BaseRepository):
    """Repository for workout tags."""

    def add(self, name: str) -> int:
        return self.execute("INSERT INTO tags (name) VALUES (?);", (name,))

    def update(self, tag_id: int, name: str) -> None:
        rows = super().fetch_all("SELECT id FROM tags WHERE id = ?;", (tag_id,))
        if not rows:
            raise ValueError("tag not found")
        self.execute("UPDATE tags SET name = ? WHERE id = ?;", (name, tag_id))

    def delete(self, tag_id: int) -> None:
        rows = super().fetch_all("SELECT id FROM tags WHERE id = ?;", (tag_id,))
        if not rows:
            raise ValueError("tag not found")
        self.execute("DELETE FROM tags WHERE id = ?;", (tag_id,))
        self.execute("DELETE FROM workout_tags WHERE tag_id = ?;", (tag_id,))

    def fetch_all(self) -> list[tuple[int, str]]:
        rows = super().fetch_all("SELECT id, name FROM tags ORDER BY name;")
        return [(r[0], r[1]) for r in rows]

    def get_id(self, name: str) -> int | None:
        rows = super().fetch_all("SELECT id FROM tags WHERE name = ?;", (name,))
        return rows[0][0] if rows else None

    def assign(self, workout_id: int, tag_id: int) -> None:
        self.execute(
            "INSERT OR IGNORE INTO workout_tags (workout_id, tag_id) VALUES (?, ?);",
            (workout_id, tag_id),
        )

    def remove(self, workout_id: int, tag_id: int) -> None:
        self.execute(
            "DELETE FROM workout_tags WHERE workout_id = ? AND tag_id = ?;",
            (workout_id, tag_id),
        )

    def fetch_for_workout(self, workout_id: int) -> list[tuple[int, str]]:
        rows = super().fetch_all(
            "SELECT t.id, t.name FROM tags t JOIN workout_tags w ON t.id = w.tag_id WHERE w.workout_id = ? ORDER BY t.name;",
            (workout_id,),
        )
        return [(r[0], r[1]) for r in rows]

    def set_tags(self, workout_id: int, tag_ids: list[int]) -> None:
        with self._connection() as conn:
            conn.execute(
                "DELETE FROM workout_tags WHERE workout_id = ?;", (workout_id,)
            )
            for tid in tag_ids:
                conn.execute(
                    "INSERT INTO workout_tags (workout_id, tag_id) VALUES (?, ?);",
                    (workout_id, tid),
                )

    # Exercise tag management

    def assign_exercise(self, exercise_name: str, tag_id: int) -> None:
        self.execute(
            "INSERT OR IGNORE INTO exercise_tags (exercise_name, tag_id) VALUES (?, ?);",
            (exercise_name, tag_id),
        )

    def remove_exercise(self, exercise_name: str, tag_id: int) -> None:
        self.execute(
            "DELETE FROM exercise_tags WHERE exercise_name = ? AND tag_id = ?;",
            (exercise_name, tag_id),
        )

    def fetch_for_exercise(self, exercise_name: str) -> list[tuple[int, str]]:
        rows = super().fetch_all(
            "SELECT t.id, t.name FROM tags t JOIN exercise_tags e ON t.id = e.tag_id WHERE e.exercise_name = ? ORDER BY t.name;",
            (exercise_name,),
        )
        return [(r[0], r[1]) for r in rows]

    def search_exercises_by_tag(self, tag: str) -> list[str]:
        rows = super().fetch_all(
            "SELECT e.exercise_name FROM exercise_tags e JOIN tags t ON e.tag_id = t.id WHERE t.name = ? ORDER BY e.exercise_name;",
            (tag,),
        )
        return [r[0] for r in rows]


class AsyncTagRepository(AsyncBaseRepository):
    """Asynchronous repository for workout tags."""

    async def add(self, name: str) -> int:
        return await self.execute("INSERT INTO tags (name) VALUES (?);", (name,))

    async def update(self, tag_id: int, name: str) -> None:
        rows = await super().fetch_all("SELECT id FROM tags WHERE id = ?;", (tag_id,))
        if not rows:
            raise ValueError("tag not found")
        await self.execute("UPDATE tags SET name = ? WHERE id = ?;", (name, tag_id))

    async def delete(self, tag_id: int) -> None:
        rows = await super().fetch_all("SELECT id FROM tags WHERE id = ?;", (tag_id,))
        if not rows:
            raise ValueError("tag not found")
        await self.execute("DELETE FROM tags WHERE id = ?;", (tag_id,))
        await self.execute("DELETE FROM workout_tags WHERE tag_id = ?;", (tag_id,))

    async def fetch_all(self) -> list[tuple[int, str]]:
        rows = await super().fetch_all("SELECT id, name FROM tags ORDER BY name;")
        return [(r[0], r[1]) for r in rows]

    async def get_id(self, name: str) -> int | None:
        rows = await super().fetch_all("SELECT id FROM tags WHERE name = ?;", (name,))
        return rows[0][0] if rows else None

    async def assign(self, workout_id: int, tag_id: int) -> None:
        await self.execute(
            "INSERT OR IGNORE INTO workout_tags (workout_id, tag_id) VALUES (?, ?);",
            (workout_id, tag_id),
        )

    async def remove(self, workout_id: int, tag_id: int) -> None:
        await self.execute(
            "DELETE FROM workout_tags WHERE workout_id = ? AND tag_id = ?;",
            (workout_id, tag_id),
        )

    async def fetch_for_workout(self, workout_id: int) -> list[tuple[int, str]]:
        rows = await super().fetch_all(
            "SELECT t.id, t.name FROM tags t JOIN workout_tags w ON t.id = w.tag_id WHERE w.workout_id = ? ORDER BY t.name;",
            (workout_id,),
        )
        return [(r[0], r[1]) for r in rows]

    async def set_tags(self, workout_id: int, tag_ids: list[int]) -> None:
        async with self._async_connection() as conn:
            await conn.execute(
                "DELETE FROM workout_tags WHERE workout_id = ?;", (workout_id,)
            )
            for tid in tag_ids:
                await conn.execute(
                    "INSERT INTO workout_tags (workout_id, tag_id) VALUES (?, ?);",
                    (workout_id, tid),
                )
            await conn.commit()

    # Exercise tag management

    async def assign_exercise(self, exercise_name: str, tag_id: int) -> None:
        await self.execute(
            "INSERT OR IGNORE INTO exercise_tags (exercise_name, tag_id) VALUES (?, ?);",
            (exercise_name, tag_id),
        )

    async def remove_exercise(self, exercise_name: str, tag_id: int) -> None:
        await self.execute(
            "DELETE FROM exercise_tags WHERE exercise_name = ? AND tag_id = ?;",
            (exercise_name, tag_id),
        )

    async def fetch_for_exercise(self, exercise_name: str) -> list[tuple[int, str]]:
        rows = await super().fetch_all(
            "SELECT t.id, t.name FROM tags t JOIN exercise_tags e ON t.id = e.tag_id WHERE e.exercise_name = ? ORDER BY t.name;",
            (exercise_name,),
        )
        return [(r[0], r[1]) for r in rows]

    async def search_exercises_by_tag(self, tag: str) -> list[str]:
        rows = await super().fetch_all(
            "SELECT e.exercise_name FROM exercise_tags e JOIN tags t ON e.tag_id = t.id WHERE t.name = ? ORDER BY e.exercise_name;",
            (tag,),
        )
        return [r[0] for r in rows]


class GoalRepository(BaseRepository):
    """Repository for goal management."""

    def __init__(self, db_path: str = "workout.db") -> None:
        super().__init__(db_path)
        self.exercise_names = ExerciseNameRepository(db_path)

    def add(
        self,
        exercise_name: str,
        name: str,
        target_value: float,
        unit: str,
        start_date: str,
        target_date: str,
    ) -> int:
        canonical = self.exercise_names.canonical(exercise_name)
        return self.execute(
            "INSERT INTO goals (exercise_name, name, target_value, unit, start_date, target_date) VALUES (?, ?, ?, ?, ?, ?);",
            (canonical, name, target_value, unit, start_date, target_date),
        )

    def update(
        self,
        goal_id: int,
        exercise_name: str | None = None,
        name: str | None = None,
        target_value: float | None = None,
        unit: str | None = None,
        start_date: str | None = None,
        target_date: str | None = None,
        achieved: bool | None = None,
    ) -> None:
        rows = super().fetch_all("SELECT id FROM goals WHERE id = ?;", (goal_id,))
        if not rows:
            raise ValueError("goal not found")
        fields = []
        params = []
        if exercise_name is not None:
            fields.append("exercise_name = ?")
            params.append(self.exercise_names.canonical(exercise_name))
        if name is not None:
            fields.append("name = ?")
            params.append(name)
        if target_value is not None:
            fields.append("target_value = ?")
            params.append(target_value)
        if unit is not None:
            fields.append("unit = ?")
            params.append(unit)
        if start_date is not None:
            fields.append("start_date = ?")
            params.append(start_date)
        if target_date is not None:
            fields.append("target_date = ?")
            params.append(target_date)
        if achieved is not None:
            fields.append("achieved = ?")
            params.append(int(achieved))
        if fields:
            params.append(goal_id)
            self.execute(
                f"UPDATE goals SET {', '.join(fields)} WHERE id = ?;",
                tuple(params),
            )

    def delete(self, goal_id: int) -> None:
        rows = super().fetch_all("SELECT id FROM goals WHERE id = ?;", (goal_id,))
        if not rows:
            raise ValueError("goal not found")
        self.execute("DELETE FROM goals WHERE id = ?;", (goal_id,))

    def fetch_all(self) -> list[tuple[int, str, str, float, str, str, str, int]]:
        rows = super().fetch_all(
            "SELECT id, exercise_name, name, target_value, unit, start_date, target_date, achieved FROM goals ORDER BY id;"
        )
        return [
            (
                r[0],
                r[1],
                r[2],
                float(r[3]),
                r[4],
                r[5],
                r[6],
                int(r[7]),
            )
            for r in rows
        ]

    def fetch(self, goal_id: int) -> dict[str, object]:
        rows = super().fetch_all(
            "SELECT id, exercise_name, name, target_value, unit, start_date, target_date, achieved FROM goals WHERE id = ?;",
            (goal_id,),
        )
        if not rows:
            raise ValueError("goal not found")
        r = rows[0]
        return {
            "id": r[0],
            "exercise_name": r[1],
            "name": r[2],
            "target_value": float(r[3]),
            "unit": r[4],
            "start_date": r[5],
            "target_date": r[6],
            "achieved": bool(r[7]),
        }

    def fetch_active_by_exercise(
        self, exercise_name: str, today: str | None = None
    ) -> list[dict[str, object]]:
        """Return active goals for ``exercise_name`` ordered by target date."""
        canonical = self.exercise_names.canonical(exercise_name)
        current = today or datetime.date.today().isoformat()
        rows = super().fetch_all(
            "SELECT id, exercise_name, name, target_value, unit, start_date, target_date, achieved "
            "FROM goals WHERE exercise_name = ? AND achieved = 0 AND start_date <= ? AND target_date >= ? "
            "ORDER BY target_date;",
            (canonical, current, current),
        )
        result = []
        for r in rows:
            result.append(
                {
                    "id": r[0],
                    "exercise_name": r[1],
                    "name": r[2],
                    "target_value": float(r[3]),
                    "unit": r[4],
                    "start_date": r[5],
                    "target_date": r[6],
                    "achieved": bool(r[7]),
                }
            )
        return result

    def fetch_all_active(self, today: str | None = None) -> list[dict[str, object]]:
        """Return all currently active goals ordered by target date."""
        current = today or datetime.date.today().isoformat()
        rows = super().fetch_all(
            "SELECT id, exercise_name, name, target_value, unit, start_date, target_date, achieved "
            "FROM goals WHERE achieved = 0 AND start_date <= ? AND target_date >= ? "
            "ORDER BY target_date;",
            (current, current),
        )
        result = []
        for r in rows:
            result.append(
                {
                    "id": r[0],
                    "exercise_name": r[1],
                    "name": r[2],
                    "target_value": float(r[3]),
                    "unit": r[4],
                    "start_date": r[5],
                    "target_date": r[6],
                    "achieved": bool(r[7]),
                }
            )
        return result

    def fetch_stale(self, today: str | None = None) -> list[dict[str, object]]:
        """Return goals past their target date and not achieved."""
        current = today or datetime.date.today().isoformat()
        rows = super().fetch_all(
            "SELECT id, exercise_name, name, target_value, unit, start_date, target_date, achieved "
            "FROM goals WHERE achieved = 0 AND target_date < ? ORDER BY target_date;",
            (current,),
        )
        result = []
        for r in rows:
            result.append(
                {
                    "id": r[0],
                    "exercise_name": r[1],
                    "name": r[2],
                    "target_value": float(r[3]),
                    "unit": r[4],
                    "start_date": r[5],
                    "target_date": r[6],
                    "achieved": bool(r[7]),
                }
            )
        return result


class AutoPlannerLogRepository(BaseRepository):
    """Repository for autoplanner run logs."""

    def log_success(self) -> int:
        return self.execute(
            "INSERT INTO autoplanner_logs (timestamp, status, message) VALUES (?, 'success', NULL);",
            (datetime.datetime.now().isoformat(),),
        )

    def log_error(self, message: str) -> int:
        return self.execute(
            "INSERT INTO autoplanner_logs (timestamp, status, message) VALUES (?, 'error', ?);",
            (datetime.datetime.now().isoformat(), message),
        )

    def last_success(self) -> Optional[str]:
        rows = self.fetch_all(
            "SELECT timestamp FROM autoplanner_logs WHERE status='success' ORDER BY id DESC LIMIT 1;"
        )
        return rows[0][0] if rows else None

    def last_errors(self, limit: int = 5) -> list[tuple[str, str]]:
        rows = self.fetch_all(
            "SELECT timestamp, message FROM autoplanner_logs WHERE status='error' ORDER BY id DESC LIMIT ?;",
            (limit,),
        )
        return [(r[0], r[1]) for r in rows]


class ExercisePrescriptionLogRepository(BaseRepository):
    """Repository for exercise prescription run logs."""

    def log_success(self) -> int:
        return self.execute(
            "INSERT INTO exercise_prescription_logs (timestamp, status, message) VALUES (?, 'success', NULL);",
            (datetime.datetime.now().isoformat(),),
        )

    def log_error(self, message: str) -> int:
        return self.execute(
            "INSERT INTO exercise_prescription_logs (timestamp, status, message) VALUES (?, 'error', ?);",
            (datetime.datetime.now().isoformat(), message),
        )

    def last_success(self) -> Optional[str]:
        rows = self.fetch_all(
            "SELECT timestamp FROM exercise_prescription_logs WHERE status='success' ORDER BY id DESC LIMIT 1;"
        )
        return rows[0][0] if rows else None

    def last_errors(self, limit: int = 5) -> list[tuple[str, str]]:
        rows = self.fetch_all(
            "SELECT timestamp, message FROM exercise_prescription_logs WHERE status='error' ORDER BY id DESC LIMIT ?;",
            (limit,),
        )
        return [(r[0], r[1]) for r in rows]


class EmailLogRepository(BaseRepository):
    """Repository for email report logs."""

    def add(self, address: str, report_range: str, summary: str, success: bool) -> int:
        return self.execute(
            "INSERT INTO email_logs (timestamp, address, report_range, summary, success) VALUES (?, ?, ?, ?, ?);",
            (
                datetime.datetime.now().isoformat(),
                address,
                report_range,
                summary,
                1 if success else 0,
            ),
        )

    def fetch_all_logs(self) -> list[dict[str, object]]:
        rows = self.fetch_all(
            "SELECT id, timestamp, address, report_range, summary, success FROM email_logs ORDER BY id;"
        )
        result: list[dict[str, object]] = []
        for r in rows:
            result.append(
                {
                    "id": r[0],
                    "timestamp": r[1],
                    "address": r[2],
                    "report_range": r[3],
                    "summary": r[4],
                    "success": bool(r[5]),
                }
            )
        return result


class MLModelStatusRepository(BaseRepository):
    """Repository tracking ML model usage timestamps."""

    def set_loaded(self, name: str) -> None:
        self.execute(
            "INSERT INTO ml_model_status (name, last_loaded) VALUES (?, ?) "
            "ON CONFLICT(name) DO UPDATE SET last_loaded=excluded.last_loaded;",
            (name, datetime.datetime.now().isoformat()),
        )

    def set_trained(self, name: str) -> None:
        self.execute(
            "INSERT INTO ml_model_status (name, last_train) VALUES (?, ?) "
            "ON CONFLICT(name) DO UPDATE SET last_train=excluded.last_train;",
            (name, datetime.datetime.now().isoformat()),
        )

    def set_prediction(self, name: str) -> None:
        self.execute(
            "INSERT INTO ml_model_status (name, last_predict) VALUES (?, ?) "
            "ON CONFLICT(name) DO UPDATE SET last_predict=excluded.last_predict;",
            (name, datetime.datetime.now().isoformat()),
        )

    def fetch(self, name: str) -> dict[str, Optional[str]]:
        rows = self.fetch_all(
            "SELECT last_loaded, last_train, last_predict FROM ml_model_status WHERE name = ?;",
            (name,),
        )
        if not rows:
            return {"last_loaded": None, "last_train": None, "last_predict": None}
        r = rows[0]
        return {
            "last_loaded": r[0],
            "last_train": r[1],
            "last_predict": r[2],
        }


class NotificationRepository(BaseRepository):
    """Repository for user notifications."""

    def add(self, message: str) -> int:
        return self.execute(
            "INSERT INTO notifications (timestamp, message, read) VALUES (?, ?, 0);",
            (datetime.datetime.now().isoformat(), message),
        )

    def fetch_all(self, unread_only: bool = False) -> list[dict[str, object]]:
        sql = "SELECT id, timestamp, message, read FROM notifications"
        if unread_only:
            sql += " WHERE read=0"
        sql += " ORDER BY id;"
        rows = super().fetch_all(sql)
        result: list[dict[str, object]] = []
        for r in rows:
            result.append(
                {
                    "id": r[0],
                    "timestamp": r[1],
                    "message": r[2],
                    "read": bool(r[3]),
                }
            )
        return result

    def mark_read(self, nid: int) -> None:
        self.execute("UPDATE notifications SET read=1 WHERE id=?;", (nid,))

    def unread_count(self) -> int:
        rows = super().fetch_all(
            "SELECT COUNT(*) FROM notifications WHERE read=0;"
        )
        return rows[0][0] if rows else 0


class WorkoutCommentRepository(BaseRepository):
    """Repository for workout comments."""

    def add(self, workout_id: int, comment: str, timestamp: str) -> int:
        return self.execute(
            "INSERT INTO workout_comments (workout_id, timestamp, comment) VALUES (?, ?, ?);",
            (workout_id, timestamp, comment),
        )

    def fetch_for_workout(self, workout_id: int) -> list[tuple[int, str, str]]:
        rows = self.fetch_all(
            "SELECT id, timestamp, comment FROM workout_comments WHERE workout_id=? ORDER BY id;",
            (workout_id,),
        )
        return [(int(r[0]), r[1], r[2]) for r in rows]


class MLTrainingRawRepository(BaseRepository):
    """Repository storing raw ML training samples."""

    def add(self, model_name: str, inputs: str, target: float) -> int:
        return self.execute(
            "INSERT INTO ml_training_raw (model_name, inputs, target) VALUES (?, ?, ?);",
            (model_name, inputs, target),
        )

    def fetch(self, model_name: str) -> list[tuple[list[float], float]]:
        rows = self.fetch_all(
            "SELECT inputs, target FROM ml_training_raw WHERE model_name=? ORDER BY id;",
            (model_name,),
        )
        result: list[tuple[list[float], float]] = []
        for inp, tgt in rows:
            values = [float(x) for x in inp.split("|") if x]
            result.append((values, float(tgt)))
        return result


class StatsCacheRepository(BaseRepository):
    """Repository managing cached statistics."""

    def fetch_weight_stats(
        self, start_date: str | None, end_date: str | None, unit: str
    ) -> dict[str, float] | None:
        row = self.fetch_all(
            "SELECT avg, min, max FROM weight_stats_cache "
            "WHERE start_date IS ? AND end_date IS ? AND unit=?;",
            (start_date, end_date, unit),
        )
        if row:
            return {
                "avg": float(row[0][0]),
                "min": float(row[0][1]),
                "max": float(row[0][2]),
            }
        return None

    def save_weight_stats(
        self,
        start_date: str | None,
        end_date: str | None,
        unit: str,
        avg: float,
        min_val: float,
        max_val: float,
    ) -> None:
        self.execute(
            "INSERT OR REPLACE INTO weight_stats_cache "
            "(start_date, end_date, unit, avg, min, max) "
            "VALUES (?, ?, ?, ?, ?, ?);",
            (start_date, end_date, unit, avg, min_val, max_val),
        )

    def clear(self) -> None:
        self._delete_all("weight_stats_cache")




