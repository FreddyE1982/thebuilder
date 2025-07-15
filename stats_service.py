import datetime
from typing import List, Optional, Dict
from db import SetRepository, ExerciseNameRepository, SettingsRepository
from tools import MathTools, ExerciseProgressEstimator


class StatisticsService:
    """Compute workout statistics for analysis."""

    def __init__(
        self,
        set_repo: SetRepository,
        name_repo: ExerciseNameRepository,
        settings_repo: SettingsRepository | None = None,
    ) -> None:
        self.sets = set_repo
        self.exercise_names = name_repo
        self.settings = settings_repo

    def _alias_names(self, exercise: Optional[str]) -> List[str]:
        if not exercise:
            return self.exercise_names.fetch_all()
        return self.exercise_names.aliases(exercise)

    def exercise_history(
        self,
        exercise: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        names = self._alias_names(exercise)
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
            with_equipment=True,
        )
        history = []
        for reps, weight, rpe, date, ex_name, eq_name in rows:
            history.append(
                {
                    "exercise": ex_name,
                    "equipment": eq_name,
                    "date": date,
                    "reps": int(reps),
                    "weight": float(weight),
                    "rpe": int(rpe),
                    "volume": int(reps) * float(weight),
                    "est_1rm": MathTools.epley_1rm(float(weight), int(reps)),
                }
            )
        return history

    def exercise_summary(
        self,
        exercise: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        names = self._alias_names(exercise)
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
            with_equipment=True,
        )
        stats: Dict[str, Dict[str, float]] = {}
        for reps, weight, rpe, date, ex_name, _ in rows:
            item = stats.setdefault(ex_name, {
                "volume": 0.0,
                "rpe_total": 0.0,
                "count": 0,
                "max_1rm": 0.0,
            })
            vol = int(reps) * float(weight)
            item["volume"] += vol
            item["rpe_total"] += int(rpe)
            item["count"] += 1
            est = MathTools.epley_1rm(float(weight), int(reps))
            if est > item["max_1rm"]:
                item["max_1rm"] = est
        result = []
        for name, data in stats.items():
            result.append(
                {
                    "exercise": name,
                    "volume": round(data["volume"], 2),
                    "avg_rpe": round(data["rpe_total"] / data["count"], 2),
                    "max_1rm": round(data["max_1rm"], 2),
                    "sets": int(data["count"]),
                }
            )
        return sorted(result, key=lambda x: x["exercise"])

    def progression(
        self,
        exercise: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        history = self.exercise_history(exercise, start_date, end_date)
        by_date: Dict[str, float] = {}
        for item in history:
            date = item["date"]
            est = item["est_1rm"]
            if date not in by_date or est > by_date[date]:
                by_date[date] = est
        return [
            {"date": d, "est_1rm": round(by_date[d], 2)} for d in sorted(by_date)
        ]

    def daily_volume(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """Return total volume and set count per day."""
        names = self.exercise_names.fetch_all()
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
        )
        by_date: Dict[str, Dict[str, float]] = {}
        for reps, weight, _rpe, date in rows:
            entry = by_date.setdefault(date, {"volume": 0.0, "sets": 0})
            entry["volume"] += int(reps) * float(weight)
            entry["sets"] += 1
        result = []
        for d in sorted(by_date):
            data = by_date[d]
            result.append(
                {
                    "date": d,
                    "volume": round(data["volume"], 2),
                    "sets": data["sets"],
                }
            )
        return result

    def progress_forecast(
        self,
        exercise: str,
        weeks: int,
        workouts_per_week: int,
    ) -> List[Dict[str, float]]:
        """Predict 1RM progression for ``exercise`` over future weeks."""
        names = self._alias_names(exercise)
        rows = self.sets.fetch_history_by_names(names)
        if not rows:
            return []

        weights = [float(r[1]) for r in rows]
        reps = [int(r[0]) for r in rows]
        rpe_scores = [int(r[2]) for r in rows]
        times = list(range(len(rows)))

        months_active = (
            self.settings.get_float("months_active", 1.0)
            if self.settings
            else 1.0
        )
        workouts_per_month = float(len(set(times)))
        body_weight = (
            self.settings.get_float("body_weight", 80.0)
            if self.settings
            else 80.0
        )

        return ExerciseProgressEstimator.predict_progress(
            weights,
            reps,
            times,
            rpe_scores,
            weeks,
            workouts_per_week,
            body_weight=body_weight,
            months_active=months_active,
            workouts_per_month=workouts_per_month,
        )

    def equipment_usage(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """Return volume and set count per equipment."""
        names = self.exercise_names.fetch_all()
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
            with_equipment=True,
        )
        stats: Dict[str, Dict[str, float]] = {}
        for reps, weight, _rpe, _date, _ex_name, eq_name in rows:
            if not eq_name:
                continue
            item = stats.setdefault(eq_name, {"volume": 0.0, "sets": 0})
            item["volume"] += int(reps) * float(weight)
            item["sets"] += 1
        result = []
        for eq in sorted(stats):
            data = stats[eq]
            result.append(
                {
                    "equipment": eq,
                    "volume": round(data["volume"], 2),
                    "sets": data["sets"],
                }
            )
        return result

    def rpe_distribution(
        self,
        exercise: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, int]]:
        """Return a distribution of RPE values for the given exercise."""
        names = self._alias_names(exercise)
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
        )
        dist: Dict[int, int] = {}
        for _reps, _weight, rpe, _date in rows:
            key = int(rpe)
            dist[key] = dist.get(key, 0) + 1
        result = []
        for r in sorted(dist):
            result.append({"rpe": r, "count": dist[r]})
        return result

    def reps_distribution(
        self,
        exercise: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, int]]:
        """Return a distribution of repetition counts."""
        names = self._alias_names(exercise)
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
        )
        dist: Dict[int, int] = {}
        for reps, _weight, _rpe, _date in rows:
            key = int(reps)
            dist[key] = dist.get(key, 0) + 1
        result = []
        for r in sorted(dist):
            result.append({"reps": r, "count": dist[r]})
        return result
