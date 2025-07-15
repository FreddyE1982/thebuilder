from db import (
    WorkoutRepository,
    ExerciseRepository,
    SetRepository,
    PlannedWorkoutRepository,
    PlannedExerciseRepository,
    PlannedSetRepository,
)


class PlannerService:
    """Handles conversion of planned workouts to actual workouts."""

    def __init__(
        self,
        workout_repo: WorkoutRepository,
        exercise_repo: ExerciseRepository,
        set_repo: SetRepository,
        plan_workout_repo: PlannedWorkoutRepository,
        plan_exercise_repo: PlannedExerciseRepository,
        plan_set_repo: PlannedSetRepository,
    ) -> None:
        self.workouts = workout_repo
        self.exercises = exercise_repo
        self.sets = set_repo
        self.planned_workouts = plan_workout_repo
        self.planned_exercises = plan_exercise_repo
        self.planned_sets = plan_set_repo

    def create_workout_from_plan(self, plan_id: int) -> int:
        _pid, date = self.planned_workouts.fetch_detail(plan_id)
        workout_id = self.workouts.create(
            date, "strength"
        )
        exercises = self.planned_exercises.fetch_for_workout(plan_id)
        for ex_id, name, equipment in exercises:
            new_ex_id = self.exercises.add(workout_id, name, equipment)
            sets = self.planned_sets.fetch_for_exercise(ex_id)
            for set_id, reps, weight, rpe in sets:
                self.sets.add(
                    new_ex_id,
                    reps,
                    weight,
                    rpe,
                    planned_set_id=set_id,
                )
        return workout_id
