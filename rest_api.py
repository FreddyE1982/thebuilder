import datetime
from fastapi import FastAPI
from db import WorkoutRepository, ExerciseRepository, SetRepository


class GymAPI:
    """Provides REST endpoints for workout logging."""

    def __init__(self, db_path: str = "workout.db") -> None:
        self.workouts = WorkoutRepository(db_path)
        self.exercises = ExerciseRepository(db_path)
        self.sets = SetRepository(db_path)
        self.app = FastAPI()
        self._setup_routes()

    def _setup_routes(self) -> None:
        @self.app.post("/workouts")
        def create_workout():
            workout_id = self.workouts.create(datetime.date.today().isoformat())
            return {"id": workout_id}

        @self.app.get("/workouts")
        def list_workouts():
            workouts = self.workouts.fetch_all_workouts()
            return [{"id": wid, "date": date} for wid, date in workouts]

        @self.app.post("/workouts/{workout_id}/exercises")
        def add_exercise(workout_id: int, name: str):
            ex_id = self.exercises.add(workout_id, name)
            return {"id": ex_id}

        @self.app.delete("/exercises/{exercise_id}")
        def delete_exercise(exercise_id: int):
            self.exercises.remove(exercise_id)
            return {"status": "deleted"}

        @self.app.get("/workouts/{workout_id}/exercises")
        def list_exercises(workout_id: int):
            exercises = self.exercises.fetch_for_workout(workout_id)
            return [{"id": ex_id, "name": name} for ex_id, name in exercises]

        @self.app.post("/exercises/{exercise_id}/sets")
        def add_set(exercise_id: int, reps: int, weight: float, rpe: int):
            set_id = self.sets.add(exercise_id, reps, weight, rpe)
            return {"id": set_id}

        @self.app.put("/sets/{set_id}")
        def update_set(set_id: int, reps: int, weight: float, rpe: int):
            self.sets.update(set_id, reps, weight, rpe)
            return {"status": "updated"}

        @self.app.delete("/sets/{set_id}")
        def delete_set(set_id: int):
            self.sets.remove(set_id)
            return {"status": "deleted"}

        @self.app.get("/exercises/{exercise_id}/sets")
        def list_sets(exercise_id: int):
            sets = self.sets.fetch_for_exercise(exercise_id)
            return [
                {"id": sid, "reps": reps, "weight": weight, "rpe": rpe}
                for sid, reps, weight, rpe in sets
            ]


api = GymAPI()
app = api.app

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app)
