from db import (
    WorkoutRepository,
    ExerciseRepository,
    SetRepository,
    PlannedWorkoutRepository,
    PlannedExerciseRepository,
    PlannedSetRepository,
    TemplateWorkoutRepository,
    TemplateExerciseRepository,
    TemplateSetRepository,
)
from gamification_service import GamificationService


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
        gamification: GamificationService | None = None,
        template_workout_repo: TemplateWorkoutRepository | None = None,
        template_exercise_repo: TemplateExerciseRepository | None = None,
        template_set_repo: TemplateSetRepository | None = None,
    ) -> None:
        self.workouts = workout_repo
        self.exercises = exercise_repo
        self.sets = set_repo
        self.planned_workouts = plan_workout_repo
        self.planned_exercises = plan_exercise_repo
        self.planned_sets = plan_set_repo
        self.gamification = gamification
        self.templates = template_workout_repo or TemplateWorkoutRepository()
        self.template_exercises = template_exercise_repo or TemplateExerciseRepository()
        self.template_sets = template_set_repo or TemplateSetRepository()

    def create_workout_from_plan(self, plan_id: int) -> int:
        _pid, date, t_type = self.planned_workouts.fetch_detail(plan_id)
        workout_id = self.workouts.create(
            date,
            t_type,
            None,
            None,
        )
        exercises = self.planned_exercises.fetch_for_workout(plan_id)
        for ex_id, name, equipment in exercises:
            new_ex_id = self.exercises.add(workout_id, name, equipment, None)
            sets = self.planned_sets.fetch_for_exercise(ex_id)
            for set_id, reps, weight, rpe in sets:
                self.sets.add(
                    new_ex_id,
                    reps,
                    weight,
                    rpe,
                    planned_set_id=set_id,
                )
                if self.gamification:
                    self.gamification.record_set(new_ex_id, reps, weight, rpe)
        return workout_id

    def duplicate_plan(self, plan_id: int, new_date: str) -> int:
        _pid, _date, t_type = self.planned_workouts.fetch_detail(plan_id)
        new_id = self.planned_workouts.create(new_date, t_type)
        exercises = self.planned_exercises.fetch_for_workout(plan_id)
        for ex_id, name, equipment in exercises:
            new_ex_id = self.planned_exercises.add(new_id, name, equipment)
            sets = self.planned_sets.fetch_for_exercise(ex_id)
            for _sid, reps, weight, rpe in sets:
                self.planned_sets.add(new_ex_id, reps, weight, rpe)
        return new_id

    def create_plan_from_template(self, template_id: int, date: str) -> int:
        _tid, _name, t_type = self.templates.fetch_detail(template_id)
        plan_id = self.planned_workouts.create(date, t_type)
        exercises = self.template_exercises.fetch_for_template(template_id)
        for ex_id, name, equipment in exercises:
            new_ex_id = self.planned_exercises.add(plan_id, name, equipment)
            sets = self.template_sets.fetch_for_exercise(ex_id)
            for _sid, reps, weight, rpe in sets:
                self.planned_sets.add(new_ex_id, reps, weight, rpe)
        return plan_id
