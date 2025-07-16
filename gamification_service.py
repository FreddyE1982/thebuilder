import math
from db import GamificationRepository, ExerciseRepository, SettingsRepository
from tools import MathTools


class GamificationService:
    """Manage optional gamification features."""

    def __init__(
        self,
        repo: GamificationRepository,
        exercise_repo: ExerciseRepository,
        settings_repo: SettingsRepository,
    ) -> None:
        self.repo = repo
        self.exercises = exercise_repo
        self.settings = settings_repo

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
        wid, _name, _eq = self.exercises.fetch_detail(exercise_id)
        pts = self._points(reps, weight, rpe)
        self.repo.add(wid, pts)

    def _points(self, reps: int, weight: float, rpe: int) -> float:
        est = MathTools.epley_1rm(weight, reps)
        return round(est * (rpe / 10.0), 2)
