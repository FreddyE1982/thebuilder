from __future__ import annotations
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
    AutoPlannerLogRepository,
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
        recommender: RecommendationService | None = None,
        log_repo: AutoPlannerLogRepository | None = None,
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
        self.recommender = recommender
        self.log_repo = log_repo

    def create_workout_from_plan(self, plan_id: int) -> int:
        _pid, date, t_type = self.planned_workouts.fetch_detail(plan_id)
        workout_id = self.workouts.create(
            date,
            t_type,
            None,
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

    def create_ai_plan(
        self,
        date: str,
        exercises: list[tuple[str, str | None]],
        training_type: str = "strength",
    ) -> int:
        if not self.recommender:
            raise ValueError("recommender not configured")
        try:
            plan_id = self.planned_workouts.create(date, training_type)
            for name, equipment in exercises:
                ex_id = self.planned_exercises.add(plan_id, name, equipment)
                presc = self.recommender.generate_prescription(name)
                for item in presc["prescription"]:
                    self.planned_sets.add(
                        ex_id,
                        int(item["reps"]),
                        float(item["weight"]),
                        int(round(item["target_rpe"])),
                    )
            if self.log_repo is not None:
                self.log_repo.log_success()
            return plan_id
        except Exception as e:
            if self.log_repo is not None:
                self.log_repo.log_error(str(e))
            raise

    def copy_workout_to_template(
        self, workout_id: int, name: str | None = None
    ) -> int:
        """Create a template from an existing workout."""
        (
            _wid,
            _date,
            _s,
            _e,
            t_type,
            _notes,
            _loc,
            _rating,
            *_,
        ) = self.workouts.fetch_detail(workout_id)
        if name is None:
            name = f"Workout {workout_id}"
        template_id = self.templates.create(name, t_type)
        exercises = self.exercises.fetch_for_workout(workout_id)
        for ex_id, ex_name, eq, _note in exercises:
            t_ex_id = self.template_exercises.add(template_id, ex_name, eq)
            sets = self.sets.fetch_for_exercise(ex_id)
            for _sid, reps, weight, rpe, _st, _et, _warm, _pos in sets:
                self.template_sets.add(t_ex_id, reps, weight, rpe)
        return template_id
