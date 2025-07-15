import datetime
from db import (
    WorkoutRepository,
    ExerciseRepository,
    SetRepository,
    ExerciseNameRepository,
    SettingsRepository,
)
from tools import ExercisePrescription


class RecommendationService:
    """Generate exercise set recommendations based on logged history."""

    def __init__(
        self,
        workout_repo: WorkoutRepository,
        exercise_repo: ExerciseRepository,
        set_repo: SetRepository,
        exercise_name_repo: ExerciseNameRepository,
        settings_repo: SettingsRepository,
    ) -> None:
        self.workouts = workout_repo
        self.exercises = exercise_repo
        self.sets = set_repo
        self.exercise_names = exercise_name_repo
        self.settings = settings_repo

    def has_history(self, exercise_name: str) -> bool:
        names = self.exercise_names.aliases(exercise_name)
        history = self.sets.fetch_history_by_names(names)
        return len(history) > 0

    def recommend_next_set(self, exercise_id: int) -> dict:
        workout_id, name, _ = self.exercises.fetch_detail(exercise_id)
        alias_names = self.exercise_names.aliases(name)
        history = self.sets.fetch_history_by_names(alias_names, with_duration=True)
        if not history:
            raise ValueError("no history for exercise")
        reps_list = [int(r[0]) for r in history]
        weight_list = [float(r[1]) for r in history]
        rpe_list = [int(r[2]) for r in history]
        durations = []
        rest_times: list[float] = []
        prev_end: datetime.datetime | None = None
        for r in history:
            start = r[4]
            end = r[5]
            if start and end:
                t0 = datetime.datetime.fromisoformat(start)
                t1 = datetime.datetime.fromisoformat(end)
                durations.append((t1 - t0).total_seconds())
                if prev_end is not None:
                    rest_times.append((t0 - prev_end).total_seconds())
                else:
                    rest_times.append(90.0)
                prev_end = t1
            else:
                durations.append(0.0)
                rest_times.append(90.0 if prev_end is None else 0.0)
        dates = [datetime.date.fromisoformat(r[3]) for r in history]
        timestamps = list(range(len(dates)))
        months_active = self.settings.get_float("months_active", 1.0)
        workouts_per_month = float(len(set(timestamps)))
        prescription = ExercisePrescription.exercise_prescription(
            weight_list,
            reps_list,
            timestamps,
            rpe_list,
            durations=durations,
            rest_times=rest_times,
            body_weight=self.settings.get_float("body_weight", 80.0),
            months_active=months_active,
            workouts_per_month=workouts_per_month,
        )
        current_sets = self.sets.fetch_for_exercise(exercise_id)
        index = len(current_sets)
        if index >= len(prescription["prescription"]):
            raise ValueError("no more sets recommended")
        data = prescription["prescription"][index]
        set_id = self.sets.add(
            exercise_id,
            int(data["reps"]),
            float(data["weight"]),
            int(round(data["target_rpe"])),
        )
        return {
            "id": set_id,
            "reps": int(data["reps"]),
            "weight": float(data["weight"]),
            "rpe": int(round(data["target_rpe"])),
        }
