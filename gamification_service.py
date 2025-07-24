import math
import datetime
from db import (
    GamificationRepository,
    ExerciseRepository,
    SettingsRepository,
    WorkoutRepository,
)
from tools import MathTools


class GamificationService:
    """Manage optional gamification features."""

    def __init__(
        self,
        repo: GamificationRepository,
        exercise_repo: ExerciseRepository,
        settings_repo: SettingsRepository,
        workout_repo: WorkoutRepository | None = None,
    ) -> None:
        self.repo = repo
        self.exercises = exercise_repo
        self.settings = settings_repo
        self.workouts = workout_repo

    def enable(self, enabled: bool) -> None:
        self.settings.set_text("game_enabled", "1" if enabled else "0")

    def is_enabled(self) -> bool:
        return self.settings.get_text("game_enabled", "0") == "1"

    def total_points(self) -> float:
        return self.repo.total_points()

    def points_by_workout(self) -> list[tuple[int, float]]:
        return self.repo.workout_totals()

    def record_set(self, exercise_id: int, reps: int, weight: float, rpe: int) -> None:
        if not self.is_enabled():
            return
        wid, _name, _eq, _note = self.exercises.fetch_detail(exercise_id)
        pts = self._points(reps, weight, rpe)
        self.repo.add(wid, pts)

    def _points(self, reps: int, weight: float, rpe: int) -> float:
        est = MathTools.epley_1rm(weight, reps)
        return round(est * (rpe / 10.0), 2)

    def workout_streak(self) -> dict[str, int]:
        """Return current and record workout streak lengths."""
        if self.workouts is None:
            return {"current": 0, "record": 0}
        rows = self.workouts.fetch_all_workouts()
        if not rows:
            return {"current": 0, "record": 0}
        dates = sorted(datetime.date.fromisoformat(r[1]) for r in rows)
        record = 1
        current = 1
        for i in range(1, len(dates)):
            gap = (dates[i] - dates[i - 1]).days
            if gap == 1:
                current += 1
            elif gap > 1:
                record = max(record, current)
                current = 1
        record = max(record, current)
        if (datetime.date.today() - dates[-1]).days > 1:
            current = 0
        return {"current": current, "record": record}
