import sqlite3
from contextlib import contextmanager
from typing import List, Tuple


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
                """CREATE TABLE IF NOT EXISTS sets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exercise_id INTEGER NOT NULL,
                    reps INTEGER NOT NULL,
                    weight REAL NOT NULL,
                    FOREIGN KEY(exercise_id) REFERENCES exercises(id) ON DELETE CASCADE
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


class WorkoutRepository(BaseRepository):
    """Repository for workout table operations."""

    def create(self, date: str) -> int:
        return self.execute("INSERT INTO workouts (date) VALUES (?);", (date,))

    def fetch_all_workouts(self) -> List[Tuple[int, str]]:
        return self.fetch_all("SELECT id, date FROM workouts ORDER BY id DESC;")


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

    def add(self, exercise_id: int, reps: int, weight: float) -> int:
        return self.execute(
            "INSERT INTO sets (exercise_id, reps, weight) VALUES (?, ?, ?);",
            (exercise_id, reps, weight),
        )

    def update(self, set_id: int, reps: int, weight: float) -> None:
        self.execute(
            "UPDATE sets SET reps = ?, weight = ? WHERE id = ?;",
            (reps, weight, set_id),
        )

    def remove(self, set_id: int) -> None:
        self.execute("DELETE FROM sets WHERE id = ?;", (set_id,))

    def fetch_for_exercise(self, exercise_id: int) -> List[Tuple[int, int, float]]:
        return self.fetch_all(
            "SELECT id, reps, weight FROM sets WHERE exercise_id = ?;",
            (exercise_id,),
        )

