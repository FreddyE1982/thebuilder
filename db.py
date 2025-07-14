import sqlite3
from contextlib import contextmanager
from typing import List, Tuple, Optional


class Database:
    """Provides SQLite connection management and schema initialization."""

    def __init__(self, db_path: str = "workout.db") -> None:
        self._db_path = db_path
        self._create_tables()

    @contextmanager
    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _create_tables(self) -> None:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS workouts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL
                );"""
            )
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS exercises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workout_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    FOREIGN KEY(workout_id) REFERENCES workouts(id) ON DELETE CASCADE
                );"""
            )
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS planned_workouts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL
                );"""
            )
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS planned_exercises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    planned_workout_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    FOREIGN KEY(planned_workout_id) REFERENCES planned_workouts(id) ON DELETE CASCADE
                );"""
            )
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS planned_sets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    planned_exercise_id INTEGER NOT NULL,
                    reps INTEGER NOT NULL,
                    weight REAL NOT NULL,
                    rpe INTEGER NOT NULL,
                    FOREIGN KEY(planned_exercise_id) REFERENCES planned_exercises(id) ON DELETE CASCADE
                );"""
            )
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS sets (
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
                );"""
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

    def add(self, workout_id: int, name: str) -> int:
        return self.execute(
            "INSERT INTO exercises (workout_id, name) VALUES (?, ?);",
            (workout_id, name),
        )

    def remove(self, exercise_id: int) -> None:
        self.execute("DELETE FROM exercises WHERE id = ?;", (exercise_id,))

    def fetch_for_workout(self, workout_id: int) -> List[Tuple[int, str]]:
        return self.fetch_all(
            "SELECT id, name FROM exercises WHERE workout_id = ?;",
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

    def add(self, workout_id: int, name: str) -> int:
        return self.execute(
            "INSERT INTO planned_exercises (planned_workout_id, name) VALUES (?, ?);",
            (workout_id, name),
        )

    def remove(self, exercise_id: int) -> None:
        self.execute(
            "DELETE FROM planned_exercises WHERE id = ?;",
            (exercise_id,),
        )

    def fetch_for_workout(self, workout_id: int) -> List[Tuple[int, str]]:
        return super().fetch_all(
            "SELECT id, name FROM planned_exercises WHERE planned_workout_id = ?;",
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

