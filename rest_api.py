import datetime
from fastapi import FastAPI
from db import (
    WorkoutRepository,
    ExerciseRepository,
    SetRepository,
    PlannedWorkoutRepository,
    PlannedExerciseRepository,
    PlannedSetRepository,
    EquipmentRepository,
)
from planner_service import PlannerService


class GymAPI:
    """Provides REST endpoints for workout logging."""

    def __init__(self, db_path: str = "workout.db") -> None:
        self.workouts = WorkoutRepository(db_path)
        self.exercises = ExerciseRepository(db_path)
        self.sets = SetRepository(db_path)
        self.planned_workouts = PlannedWorkoutRepository(db_path)
        self.planned_exercises = PlannedExerciseRepository(db_path)
        self.planned_sets = PlannedSetRepository(db_path)
        self.equipment = EquipmentRepository(db_path)
        self.planner = PlannerService(
            self.workouts,
            self.exercises,
            self.sets,
            self.planned_workouts,
            self.planned_exercises,
            self.planned_sets,
        )
        self.app = FastAPI()
        self._setup_routes()

    def _setup_routes(self) -> None:
        @self.app.get("/equipment/types")
        def list_equipment_types():
            return self.equipment.fetch_types()

        @self.app.get("/equipment")
        def list_equipment(equipment_type: str = None, prefix: str = None):
            return self.equipment.fetch_names(equipment_type, prefix)

        @self.app.get("/equipment/{name}")
        def get_equipment(name: str):
            muscles = self.equipment.fetch_muscles(name)
            rows = self.equipment.fetch_all(
                "SELECT equipment_type FROM equipment WHERE name = ?;", (name,)
            )
            eq_type = rows[0][0] if rows else None
            return {"name": name, "type": eq_type, "muscles": muscles}

        @self.app.post("/workouts")
        def create_workout():
            workout_id = self.workouts.create(datetime.date.today().isoformat())
            return {"id": workout_id}

        @self.app.get("/workouts")
        def list_workouts():
            workouts = self.workouts.fetch_all_workouts()
            return [{"id": wid, "date": date} for wid, date in workouts]

        @self.app.post("/workouts/{workout_id}/exercises")
        def add_exercise(workout_id: int, name: str, equipment: str = None):
            ex_id = self.exercises.add(workout_id, name, equipment)
            return {"id": ex_id}

        @self.app.delete("/exercises/{exercise_id}")
        def delete_exercise(exercise_id: int):
            self.exercises.remove(exercise_id)
            return {"status": "deleted"}

        @self.app.get("/workouts/{workout_id}/exercises")
        def list_exercises(workout_id: int):
            exercises = self.exercises.fetch_for_workout(workout_id)
            return [
                {"id": ex_id, "name": name, "equipment": eq}
                for ex_id, name, eq in exercises
            ]

        @self.app.post("/planned_workouts")
        def create_planned_workout(date: str):
            plan_id = self.planned_workouts.create(date)
            return {"id": plan_id}

        @self.app.get("/planned_workouts")
        def list_planned_workouts():
            plans = self.planned_workouts.fetch_all()
            return [{"id": pid, "date": date} for pid, date in plans]

        @self.app.post("/planned_workouts/{plan_id}/exercises")
        def add_planned_exercise(plan_id: int, name: str, equipment: str = None):
            ex_id = self.planned_exercises.add(plan_id, name, equipment)
            return {"id": ex_id}

        @self.app.get("/planned_workouts/{plan_id}/exercises")
        def list_planned_exercises(plan_id: int):
            exercises = self.planned_exercises.fetch_for_workout(plan_id)
            return [
                {"id": ex_id, "name": name, "equipment": eq}
                for ex_id, name, eq in exercises
            ]

        @self.app.delete("/planned_exercises/{exercise_id}")
        def delete_planned_exercise(exercise_id: int):
            self.planned_exercises.remove(exercise_id)
            return {"status": "deleted"}

        @self.app.post("/planned_exercises/{exercise_id}/sets")
        def add_planned_set(exercise_id: int, reps: int, weight: float, rpe: int):
            set_id = self.planned_sets.add(exercise_id, reps, weight, rpe)
            return {"id": set_id}

        @self.app.get("/planned_exercises/{exercise_id}/sets")
        def list_planned_sets(exercise_id: int):
            sets = self.planned_sets.fetch_for_exercise(exercise_id)
            return [
                {"id": sid, "reps": reps, "weight": weight, "rpe": rpe}
                for sid, reps, weight, rpe in sets
            ]

        @self.app.delete("/planned_sets/{set_id}")
        def delete_planned_set(set_id: int):
            self.planned_sets.remove(set_id)
            return {"status": "deleted"}

        @self.app.post("/planned_workouts/{plan_id}/use")
        def use_planned_workout(plan_id: int):
            workout_id = self.planner.create_workout_from_plan(plan_id)
            return {"id": workout_id}

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

        @self.app.get("/sets/{set_id}")
        def get_set(set_id: int):
            return self.sets.fetch_detail(set_id)

        @self.app.get("/exercises/{exercise_id}/sets")
        def list_sets(exercise_id: int):
            sets = self.sets.fetch_for_exercise(exercise_id)
            return [
                {"id": sid, "reps": reps, "weight": weight, "rpe": rpe}
                for sid, reps, weight, rpe in sets
            ]

        @self.app.post("/settings/delete_all")
        def delete_all(confirmation: str):
            if confirmation != "Yes, I confirm":
                return {"status": "confirmation_failed"}
            self.workouts.delete_all()
            self.planned_workouts.delete_all()
            return {"status": "deleted"}

        @self.app.post("/settings/delete_logged")
        def delete_logged(confirmation: str):
            if confirmation != "Yes, I confirm":
                return {"status": "confirmation_failed"}
            self.workouts.delete_all()
            return {"status": "deleted"}

        @self.app.post("/settings/delete_planned")
        def delete_planned(confirmation: str):
            if confirmation != "Yes, I confirm":
                return {"status": "confirmation_failed"}
            self.planned_workouts.delete_all()
            return {"status": "deleted"}


api = GymAPI()
app = api.app

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app)
