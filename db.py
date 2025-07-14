import sqlite3
import csv
import os
from contextlib import contextmanager
from typing import List, Tuple, Optional, Iterable


class Database:
    """Provides SQLite connection management and schema initialization."""

    _TABLE_DEFINITIONS = {
        "workouts": (
            """CREATE TABLE workouts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL
                );""",
            ["id", "date"],
        ),
        "equipment": (
            """CREATE TABLE equipment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    equipment_type TEXT NOT NULL,
                    name TEXT NOT NULL UNIQUE,
                    muscles TEXT NOT NULL
                );""",
            ["id", "equipment_type", "name", "muscles"],
        ),
        "exercises": (
            """CREATE TABLE exercises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workout_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    equipment_name TEXT,
                    FOREIGN KEY(workout_id) REFERENCES workouts(id) ON DELETE CASCADE,
                    FOREIGN KEY(equipment_name) REFERENCES equipment(name)
                );""",
            ["id", "workout_id", "name", "equipment_name"],
        ),
        "planned_workouts": (
            """CREATE TABLE planned_workouts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL
                );""",
            ["id", "date"],
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
        "sets": (
            """CREATE TABLE sets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exercise_id INTEGER NOT NULL,
                    reps INTEGER NOT NULL,
                    weight REAL NOT NULL,
                    rpe INTEGER NOT NULL,
                    planned_set_id INTEGER,
                    diff_reps INTEGER NOT NULL DEFAULT 0,
                    diff_weight REAL NOT NULL DEFAULT 0,
                    diff_rpe INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(exercise_id) REFERENCES exercises(id) ON DELETE CASCADE,
                    FOREIGN KEY(planned_set_id) REFERENCES planned_sets(id) ON DELETE SET NULL
                );""",
            [
                "id",
                "exercise_id",
                "reps",
                "weight",
                "rpe",
                "planned_set_id",
                "diff_reps",
                "diff_weight",
                "diff_rpe",
            ],
        ),
    }

    def __init__(self, db_path: str = "workout.db") -> None:
        self._db_path = db_path
        self._ensure_schema()
        self._import_equipment_data()

    @contextmanager
    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _ensure_schema(self) -> None:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys=off;")
            for table, (sql, columns) in self._TABLE_DEFINITIONS.items():
                self._ensure_table(conn, table, sql, columns)
            cursor.execute("PRAGMA foreign_keys=on;")

    def _ensure_table(
        self, conn: sqlite3.Connection, table: str, sql: str, columns: List[str]
    ) -> None:
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
            conn.execute(
                f"INSERT INTO {table} ({cols}) SELECT {cols} FROM {table}_old;"
            )
        conn.execute(f"DROP TABLE {table}_old;")

    def _import_equipment_data(self) -> None:
        csv_path = os.path.join(os.path.dirname(__file__), "table3_equipment_muscles.csv")
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
                    "INSERT INTO equipment (equipment_type, name, muscles) VALUES (?, ?, ?) "
                    "ON CONFLICT(name) DO UPDATE SET equipment_type=excluded.equipment_type, muscles=excluded.muscles;",
                    (equipment_type, name, muscles),
                )


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


class WorkoutRepository(BaseRepository):
    """Repository for workout table operations."""

    def create(self, date: str) -> int:
        return self.execute("INSERT INTO workouts (date) VALUES (?);", (date,))

    def fetch_all_workouts(self) -> List[Tuple[int, str]]:
        return self.fetch_all("SELECT id, date FROM workouts ORDER BY id DESC;")

    def delete_all(self) -> None:
        self._delete_all("workouts")


class ExerciseRepository(BaseRepository):
    """Repository for exercise table operations."""

    def add(
        self, workout_id: int, name: str, equipment_name: Optional[str] = None
    ) -> int:
        return self.execute(
            "INSERT INTO exercises (workout_id, name, equipment_name) VALUES (?, ?, ?);",
            (workout_id, name, equipment_name),
        )

    def remove(self, exercise_id: int) -> None:
        self.execute("DELETE FROM exercises WHERE id = ?;", (exercise_id,))

    def fetch_for_workout(self, workout_id: int) -> List[Tuple[int, str, Optional[str]]]:
        return self.fetch_all(
            "SELECT id, name, equipment_name FROM exercises WHERE workout_id = ?;",
            (workout_id,),
        )


class SetRepository(BaseRepository):
    """Repository for sets table operations."""

    def add(
        self,
        exercise_id: int,
        reps: int,
        weight: float,
        rpe: int,
        planned_set_id: Optional[int] = None,
        diff_reps: int = 0,
        diff_weight: float = 0.0,
        diff_rpe: int = 0,
    ) -> int:
        return self.execute(
            "INSERT INTO sets (exercise_id, reps, weight, rpe, planned_set_id, diff_reps, diff_weight, diff_rpe) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
            (exercise_id, reps, weight, rpe, planned_set_id, diff_reps, diff_weight, diff_rpe),
        )

    def update(self, set_id: int, reps: int, weight: float, rpe: int) -> None:
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
        self.execute(
            "UPDATE sets SET reps = ?, weight = ?, rpe = ?, diff_reps = ?, diff_weight = ?, diff_rpe = ? "
            "WHERE id = ?;",
            (reps, weight, rpe, diff_reps, diff_weight, diff_rpe, set_id),
        )

    def remove(self, set_id: int) -> None:
        self.execute("DELETE FROM sets WHERE id = ?;", (set_id,))

    def fetch_for_exercise(self, exercise_id: int) -> List[Tuple[int, int, float, int]]:
        return self.fetch_all(
            "SELECT id, reps, weight, rpe FROM sets WHERE exercise_id = ?;",
            (exercise_id,),
        )

    def fetch_detail(self, set_id: int) -> dict:
        rows = self.fetch_all(
            "SELECT id, reps, weight, rpe, planned_set_id, diff_reps, diff_weight, diff_rpe FROM sets WHERE id = ?;",
            (set_id,),
        )
        sid, reps, weight, rpe, planned_set_id, diff_reps, diff_weight, diff_rpe = rows[0]
        return {
            "id": sid,
            "reps": reps,
            "weight": weight,
            "rpe": rpe,
            "planned_set_id": planned_set_id,
            "diff_reps": diff_reps,
            "diff_weight": diff_weight,
            "diff_rpe": diff_rpe,
        }


class PlannedWorkoutRepository(BaseRepository):
    """Repository for planned workouts."""

    def create(self, date: str) -> int:
        return self.execute(
            "INSERT INTO planned_workouts (date) VALUES (?);",
            (date,),
        )

    def fetch_all(self) -> List[Tuple[int, str]]:
        return super().fetch_all(
            "SELECT id, date FROM planned_workouts ORDER BY id DESC;"
        )

    def delete_all(self) -> None:
        self._delete_all("planned_workouts")


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

    def fetch_for_workout(self, workout_id: int) -> List[Tuple[int, str, Optional[str]]]:
        return super().fetch_all(
            "SELECT id, name, equipment_name FROM planned_exercises WHERE planned_workout_id = ?;",
            (workout_id,),
        )


class PlannedSetRepository(BaseRepository):
    """Repository for planned sets."""

    def add(self, exercise_id: int, reps: int, weight: float, rpe: int) -> int:
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


class EquipmentRepository(BaseRepository):
    """Repository for equipment data."""

    def upsert_many(self, records: Iterable[Tuple[str, str, str]]) -> None:
        for equipment_type, name, muscles in records:
            self.execute(
                "INSERT INTO equipment (equipment_type, name, muscles) VALUES (?, ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET equipment_type=excluded.equipment_type, muscles=excluded.muscles;",
                (equipment_type, name, muscles),
            )

    def fetch_types(self) -> List[str]:
        rows = self.fetch_all(
            "SELECT DISTINCT equipment_type FROM equipment ORDER BY equipment_type;"
        )
        return [r[0] for r in rows]

    def fetch_names(
        self, equipment_type: Optional[str] = None, prefix: Optional[str] = None
    ) -> List[str]:
        query = "SELECT name FROM equipment WHERE 1=1"
        params: List[str] = []
        if equipment_type:
            query += " AND equipment_type = ?"
            params.append(equipment_type)
        if prefix:
            query += " AND name LIKE ?"
            params.append(f"{prefix}%")
        query += " ORDER BY name;"
        rows = self.fetch_all(query, tuple(params))
        return [r[0] for r in rows]

    def fetch_muscles(self, name: str) -> List[str]:
        rows = self.fetch_all("SELECT muscles FROM equipment WHERE name = ?;", (name,))
        if rows:
            return rows[0][0].split("|")
        return []

