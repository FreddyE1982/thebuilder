import sqlite3
import csv
import os
import io
from contextlib import contextmanager
from typing import List, Tuple, Optional, Iterable, Set


class Database:
    """Provides SQLite connection management and schema initialization."""

    _TABLE_DEFINITIONS = {
        "workouts": (
            """CREATE TABLE workouts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    start_time TEXT,
                    end_time TEXT,
                    training_type TEXT NOT NULL DEFAULT 'strength'
                );""",
            ["id", "date", "start_time", "end_time", "training_type"],
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
        "muscles": (
            """CREATE TABLE muscles (
                    name TEXT PRIMARY KEY,
                    canonical_name TEXT NOT NULL
                );""",
            ["name", "canonical_name"],
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
                "is_custom",
            ],
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
                    start_time TEXT,
                    end_time TEXT,
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
                "start_time",
                "end_time",
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
    }

    def __init__(self, db_path: str = "workout.db") -> None:
        self._db_path = db_path
        self._ensure_schema()
        self._import_equipment_data()
        self._import_exercise_catalog_data()
        self._sync_muscles()
        self._sync_exercise_names()
        self._init_settings()

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
                    "INSERT INTO equipment (equipment_type, name, muscles, is_custom) VALUES (?, ?, ?, 0) "
                    "ON CONFLICT(name) DO UPDATE SET equipment_type=excluded.equipment_type, muscles=excluded.muscles;",
                    (equipment_type, name, muscles),
                )

    def _import_exercise_catalog_data(self) -> None:
        csv_path = os.path.join(os.path.dirname(__file__), "table1_exercise_database.csv")
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
        defaults = {"body_weight": "80.0", "months_active": "1"}
        with self._connection() as conn:
            for key, value in defaults.items():
                conn.execute(
                    "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?);",
                    (key, value),
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

    def create(self, date: str, training_type: str = "strength") -> int:
        return self.execute(
            "INSERT INTO workouts (date, training_type) VALUES (?, ?);",
            (date, training_type),
        )

    def fetch_all_workouts(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Tuple[int, str, Optional[str], Optional[str], str]]:
        query = (
            "SELECT id, date, start_time, end_time, training_type FROM workouts"
        )
        params: list[str] = []
        if start_date:
            query += " WHERE date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?" if start_date else " WHERE date <= ?"
            params.append(end_date)
        query += " ORDER BY id DESC;"
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

    def fetch_detail(
        self, workout_id: int
    ) -> Tuple[int, str, Optional[str], Optional[str], str]:
        rows = self.fetch_all(
            "SELECT id, date, start_time, end_time, training_type FROM workouts WHERE id = ?;",
            (workout_id,),
        )
        if not rows:
            raise ValueError("workout not found")
        return rows[0]

    def delete_all(self) -> None:
        self._delete_all("workouts")


class ExerciseRepository(BaseRepository):
    """Repository for exercise table operations."""

    def __init__(self, db_path: str = "workout.db") -> None:
        super().__init__(db_path)
        self.exercise_names = ExerciseNameRepository(db_path)

    def add(
        self, workout_id: int, name: str, equipment_name: Optional[str] = None
    ) -> int:
        self.exercise_names.ensure([name])
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

    def fetch_detail(self, exercise_id: int) -> Tuple[int, str, Optional[str]]:
        rows = self.fetch_all(
            "SELECT workout_id, name, equipment_name FROM exercises WHERE id = ?;",
            (exercise_id,),
        )
        if not rows:
            raise ValueError("exercise not found")
        return rows[0]


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

    def fetch_for_exercise(self, exercise_id: int) -> List[Tuple[int, int, float, int, Optional[str], Optional[str]]]:
        return self.fetch_all(
            "SELECT id, reps, weight, rpe, start_time, end_time FROM sets WHERE exercise_id = ?;",
            (exercise_id,),
        )

    def fetch_detail(self, set_id: int) -> dict:
        rows = self.fetch_all(
            "SELECT id, reps, weight, rpe, planned_set_id, diff_reps, diff_weight, diff_rpe, start_time, end_time FROM sets WHERE id = ?;",
            (set_id,),
        )
        (
            sid,
            reps,
            weight,
            rpe,
            planned_set_id,
            diff_reps,
            diff_weight,
            diff_rpe,
            start_time,
            end_time,
        ) = rows[0]
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
        }

    def fetch_history_by_names(
        self,
        names: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        equipment: Optional[List[str]] = None,
        with_equipment: bool = False,
        with_duration: bool = False,
        with_workout_id: bool = False,
    ) -> List[Tuple]:
        placeholders = ", ".join(["?" for _ in names])
        select = "SELECT s.reps, s.weight, s.rpe, w.date"
        if with_equipment:
            select += ", e.name, e.equipment_name"
        if with_duration:
            select += ", s.start_time, s.end_time"
        if with_workout_id:
            select += ", w.id"
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
    ) -> List[
        Tuple[str, Optional[str], int, float, int, Optional[str], Optional[str]]
    ]:
        return self.fetch_all(
            "SELECT e.name, e.equipment_name, s.reps, s.weight, s.rpe,"
            " s.start_time, s.end_time "
            "FROM sets s JOIN exercises e ON s.exercise_id = e.id "
            "WHERE e.workout_id = ? ORDER BY e.id, s.id;",
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

    def fetch_detail(self, plan_id: int) -> Tuple[int, str]:
        rows = super().fetch_all(
            "SELECT id, date FROM planned_workouts WHERE id = ?;",
            (plan_id,),
        )
        if not rows:
            raise ValueError("planned workout not found")
        return rows[0]

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


class SettingsRepository(BaseRepository):
    """Repository for general application settings."""

    def get_float(self, key: str, default: float) -> float:
        rows = self.fetch_all("SELECT value FROM settings WHERE key = ?;", (key,))
        return float(rows[0][0]) if rows else default

    def set_float(self, key: str, value: float) -> None:
        self.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value;",
            (key, str(value)),
        )

    def all_settings(self) -> dict:
        rows = self.fetch_all("SELECT key, value FROM settings ORDER BY key;")
        return {k: float(v) for k, v in rows}


class EquipmentRepository(BaseRepository):
    """Repository for equipment data."""

    def __init__(self, db_path: str = "workout.db") -> None:
        super().__init__(db_path)
        self.muscles = MuscleRepository(db_path)

    def upsert_many(self, records: Iterable[Tuple[str, str, str]]) -> None:
        for equipment_type, name, muscles in records:
            self.muscles.ensure(muscles.split("|"))
            self.execute(
                "INSERT INTO equipment (equipment_type, name, muscles, is_custom) VALUES (?, ?, ?, 0) "
                "ON CONFLICT(name) DO UPDATE SET equipment_type=excluded.equipment_type, muscles=excluded.muscles;",
                (equipment_type, name, muscles),
            )

    def fetch_types(self) -> List[str]:
        rows = self.fetch_all(
            "SELECT DISTINCT equipment_type FROM equipment ORDER BY equipment_type;"
        )
        return [r[0] for r in rows]

    def fetch_names(
        self,
        equipment_type: Optional[str] = None,
        prefix: Optional[str] = None,
        muscles: Optional[List[str]] = None,
    ) -> List[str]:
        query = "SELECT name FROM equipment WHERE 1=1"
        params: List[str] = []
        if equipment_type:
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
        return self.fetch_all(
            "SELECT name, equipment_type, muscles, is_custom FROM equipment ORDER BY name;"
        )

    def fetch_all_muscles(self) -> List[str]:
        rows = self.fetch_all("SELECT muscles FROM equipment;")
        muscles: Set[str] = set()
        for row in rows:
            for m in row[0].split("|"):
                muscles.add(self.muscles.canonical(m))
        return sorted(muscles)

    def add(self, equipment_type: str, name: str, muscles: List[str]) -> int:
        existing = self.fetch_all(
            "SELECT is_custom FROM equipment WHERE name = ?;",
            (name,),
        )
        if existing:
            raise ValueError("equipment exists")
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

    def __init__(self, db_path: str = "workout.db") -> None:
        super().__init__(db_path)
        self.muscles = MuscleRepository(db_path)
        self.exercise_names = ExerciseNameRepository(db_path)

    def fetch_muscle_groups(self) -> List[str]:
        rows = self.fetch_all(
            "SELECT DISTINCT muscle_group FROM exercise_catalog ORDER BY muscle_group;"
        )
        return [r[0] for r in rows]

    def fetch_names(
        self,
        muscle_groups: Optional[List[str]] = None,
        muscles: Optional[List[str]] = None,
        equipment: Optional[str] = None,
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
        query += " ORDER BY name;"
        rows = self.fetch_all(query, tuple(params))
        result: List[str] = []
        for (name,) in rows:
            result.extend(self.exercise_names.aliases(name))
        return sorted(dict.fromkeys(result))

    def fetch_detail(self, name: str) -> Optional[Tuple[str, str, str, str, str, str, str]]:
        canonical = self.exercise_names.canonical(name)
        rows = self.fetch_all(
            "SELECT muscle_group, variants, equipment_names, primary_muscle, secondary_muscle, tertiary_muscle, other_muscles, is_custom FROM exercise_catalog WHERE name = ?;",
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
                is_custom,
            )
        return None

    def fetch_all_records(self) -> List[Tuple[str, str, str, str, str, str, str, int]]:
        rows = self.fetch_all(
            "SELECT name, muscle_group, variants, equipment_names, primary_muscle, secondary_muscle, tertiary_muscle, other_muscles, is_custom FROM exercise_catalog ORDER BY name;"
        )
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
                    is_custom,
                )
            )
        return result

    def fetch_all_muscles(self) -> List[str]:
        rows = self.fetch_all(
            "SELECT primary_muscle, secondary_muscle, tertiary_muscle, other_muscles FROM exercise_catalog;"
        )
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
    ) -> int:
        existing = self.fetch_all(
            "SELECT is_custom FROM exercise_catalog WHERE name = ?;",
            (name,),
        )
        if existing:
            raise ValueError("exercise exists")
        self.exercise_names.ensure([name])
        muscs = [primary_muscle] + secondary_muscle.split("|") + tertiary_muscle.split("|") + other_muscles.split("|")
        self.muscles.ensure([m for m in muscs if m])
        primary_muscle = self.muscles.canonical(primary_muscle)
        secondary_muscle = "|".join([
            self.muscles.canonical(m) for m in secondary_muscle.split("|") if m
        ])
        tertiary_muscle = "|".join([
            self.muscles.canonical(m) for m in tertiary_muscle.split("|") if m
        ])
        other_muscles = "|".join([
            self.muscles.canonical(m) for m in other_muscles.split("|") if m
        ])
        return self.execute(
            "INSERT INTO exercise_catalog (muscle_group, name, variants, equipment_names, primary_muscle, secondary_muscle, tertiary_muscle, other_muscles, is_custom) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1);",
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
        muscs = [primary_muscle] + secondary_muscle.split("|") + tertiary_muscle.split("|") + other_muscles.split("|")
        self.muscles.ensure([m for m in muscs if m])
        primary_muscle = self.muscles.canonical(primary_muscle)
        secondary_muscle = "|".join([
            self.muscles.canonical(m) for m in secondary_muscle.split("|") if m
        ])
        tertiary_muscle = "|".join([
            self.muscles.canonical(m) for m in tertiary_muscle.split("|") if m
        ])
        other_muscles = "|".join([
            self.muscles.canonical(m) for m in other_muscles.split("|") if m
        ])
        self.execute(
            "UPDATE exercise_catalog SET muscle_group = ?, name = ?, variants = ?, equipment_names = ?, primary_muscle = ?, secondary_muscle = ?, tertiary_muscle = ?, other_muscles = ? WHERE name = ?;",
            (
                muscle_group,
                target,
                variants,
                equipment_names,
                primary_muscle,
                secondary_muscle,
                tertiary_muscle,
                other_muscles,
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
        return super().fetch_all(
            "SELECT id, date FROM pyramid_tests ORDER BY id DESC;"
        )

    def fetch_all_full(self) -> List[Tuple]:
        return super().fetch_all(
            "SELECT id, exercise_name, date, equipment_name, starting_weight, failed_weight, max_achieved, test_duration_minutes, rest_between_attempts, rpe_per_attempt, time_of_day, sleep_hours, stress_level, nutrition_quality FROM pyramid_tests ORDER BY id DESC;"
        )

    def fetch_all_with_weights(self, entries: 'PyramidEntryRepository') -> List[Tuple[int, str, List[float]]]:
        tests = self.fetch_all()
        result = []
        for tid, date in tests:
            weights = entries.fetch_for_test(tid)
            result.append((tid, date, weights))
        return result

    def fetch_full_with_weights(self, entries: 'PyramidEntryRepository') -> List[Tuple]:
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

