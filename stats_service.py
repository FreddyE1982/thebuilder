from __future__ import annotations
import datetime
from typing import List, Optional, Dict
from db import (
    SetRepository,
    ExerciseNameRepository,
    SettingsRepository,
    BodyWeightRepository,
    EquipmentRepository,
    WellnessRepository,
    HeartRateRepository,
    GoalRepository,
    StatsCacheRepository,
)
from ml_service import (
    VolumeModelService,
    ReadinessModelService,
    ProgressModelService,
    InjuryRiskModelService,
    AdaptationModelService,
)
from tools import MathTools, ExerciseProgressEstimator, ExercisePrescription


class StatisticsService:
    """Compute workout statistics for analysis."""

    def __init__(
        self,
        set_repo: SetRepository,
        name_repo: ExerciseNameRepository,
        settings_repo: SettingsRepository | None = None,
        volume_model: "VolumeModelService" | None = None,
        readiness_model: "ReadinessModelService" | None = None,
        progress_model: "ProgressModelService" | None = None,
        injury_model: "InjuryRiskModelService" | None = None,
        adaptation_model: "AdaptationModelService" | None = None,
        body_weight_repo: "BodyWeightRepository" | None = None,
        equipment_repo: "EquipmentRepository" | None = None,
        wellness_repo: "WellnessRepository" | None = None,
        catalog_repo: "ExerciseCatalogRepository" | None = None,
        workout_repo: "WorkoutRepository" | None = None,
        heart_rate_repo: "HeartRateRepository" | None = None,
        goal_repo: "GoalRepository" | None = None,
        cache_repo: "StatsCacheRepository" | None = None,
    ) -> None:
        self.sets = set_repo
        self.exercise_names = name_repo
        self.settings = settings_repo
        self.volume_model = volume_model
        self.readiness_model = readiness_model
        self.progress_model = progress_model
        self.injury_model = injury_model
        self.adaptation_model = adaptation_model
        self.body_weights = body_weight_repo
        self.equipment = equipment_repo
        self.wellness = wellness_repo
        self.catalog = catalog_repo
        self.workouts = workout_repo
        self.heart_rates = heart_rate_repo
        self.goals = goal_repo
        self.stats_cache = cache_repo
        self._cache: dict[tuple, dict] = {}

    def clear_cache(self) -> None:
        """Clear any cached statistics."""
        self._cache.clear()
        if self.stats_cache is not None:
            self.stats_cache.clear()

    def _current_body_weight(self) -> float:
        """Fetch the latest logged body weight or fallback to settings."""
        if self.body_weights is not None:
            latest = self.body_weights.fetch_latest_weight()
            if latest is not None:
                return latest
        if self.settings is not None:
            return self.settings.get_float("body_weight", 80.0)
        return 80.0

    @staticmethod
    def _parse_timestamp(ts: str) -> datetime.datetime:
        """Return ``ts`` as timezone-aware datetime in UTC."""
        dt = datetime.datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt

    def _all_names(self) -> List[str]:
        names = self.exercise_names.fetch_all()
        if (
            self.settings is not None
            and self.settings.get_bool("hide_preconfigured_exercises", False)
            and self.catalog is not None
        ):
            filtered: list[str] = []
            for n in names:
                detail = self.catalog.fetch_detail(n)
                if detail is not None and detail[-1] == 0:
                    continue
                filtered.append(n)
            return filtered
        return names

    def _alias_names(self, exercise: Optional[str]) -> List[str]:
        if not exercise:
            return self._all_names()
        if (
            self.settings is not None
            and self.settings.get_bool("hide_preconfigured_exercises", False)
            and self.catalog is not None
        ):
            detail = self.catalog.fetch_detail(exercise)
            if detail is not None and detail[-1] == 0:
                return []
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
            with_duration=True,
        )
        history = []
        for reps, weight, rpe, date, ex_name, eq_name, start, end in rows:
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
                    "velocity": MathTools.estimate_velocity_from_set(
                        int(reps), start, end
                    ),
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
            item = stats.setdefault(
                ex_name,
                {
                    "volume": 0.0,
                    "rpe_total": 0.0,
                    "count": 0,
                    "max_1rm": 0.0,
                },
            )
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
        return [{"date": d, "est_1rm": round(by_date[d], 2)} for d in sorted(by_date)]

    def muscle_progression(
        self,
        muscle: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """Return estimated 1RM progression aggregated for a muscle."""
        if self.catalog is None:
            return []
        names = self.catalog.fetch_names(muscles=[muscle])
        all_names: list[str] = []
        for n in names:
            all_names.extend(self.exercise_names.aliases(n))
        uniq = sorted(dict.fromkeys(all_names))
        rows = self.sets.fetch_history_by_names(
            uniq,
            start_date=start_date,
            end_date=end_date,
        )
        by_date: Dict[str, float] = {}
        for reps, weight, _rpe, date in rows:
            est = MathTools.epley_1rm(float(weight), int(reps))
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
        names = self._all_names()
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

    def daily_muscle_group_volume(
        self,
        muscle_group: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """Return daily volume and set count for a muscle group."""
        if self.catalog is None:
            return []
        names = self.catalog.fetch_names([muscle_group])
        all_names: list[str] = []
        for n in names:
            all_names.extend(self.exercise_names.aliases(n))
        uniq = sorted(dict.fromkeys(all_names))
        rows = self.sets.fetch_history_by_names(
            uniq,
            start_date=start_date,
            end_date=end_date,
        )
        by_date: Dict[str, Dict[str, float]] = {}
        for reps, weight, _rpe, date in rows:
            entry = by_date.setdefault(date, {"volume": 0.0, "sets": 0})
            entry["volume"] += int(reps) * float(weight)
            entry["sets"] += 1
        result: List[Dict[str, float]] = []
        for d in sorted(by_date):
            data = by_date[d]
            result.append(
                {"date": d, "volume": round(data["volume"], 2), "sets": data["sets"]}
            )
        return result

    def workouts_by_muscle_group(self, muscle_group: str) -> list[int]:
        """Return workout IDs containing exercises for the given muscle group."""
        if self.catalog is None:
            return []
        names = self.catalog.fetch_names([muscle_group])
        all_names: list[str] = []
        for n in names:
            all_names.extend(self.exercise_names.aliases(n))
        uniq = sorted(dict.fromkeys(all_names))
        rows = self.sets.fetch_history_by_names(uniq, with_workout_id=True)
        ids = sorted({r[-1] for r in rows})
        return ids

    def deload_recommendation(
        self,
        exercise: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, float]:
        """Return deload trigger and score for ``exercise``."""
        names = self._alias_names(exercise)
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
            with_duration=True,
        )
        if not rows:
            return {"trigger": 0.0, "score": 0.0}

        weights = [float(r[1]) for r in rows]
        reps = [int(r[0]) for r in rows]
        rpe_scores = [int(r[2]) for r in rows]
        durations: List[float] = []
        for _r, _w, _rpe, _date, start, end in rows:
            if start and end:
                t0 = self._parse_timestamp(start)
                t1 = self._parse_timestamp(end)
                durations.append((t1 - t0).total_seconds())
            else:
                durations.append(50.0)

        times = list(range(len(rows)))
        perf = ExercisePrescription._performance_scores_from_logs(
            weights, reps, times, 600
        )
        perf_factor = float(sum(perf) / len(perf))
        rec_factor = 1.0
        tut_ratio = float(sum(durations)) / (50.0 * len(durations))
        trigger = ExercisePrescription._deload_trigger(
            perf_factor, rpe_scores, rec_factor, tut_ratio
        )
        ac_ratio = ExercisePrescription._ac_ratio(weights, reps)
        body_weight = self._current_body_weight()
        rec_quality = ExercisePrescription._comprehensive_recovery_quality(
            None, None, None, body_weight
        )
        rpe_factor = (
            sum(rpe_scores[-3:]) / len(rpe_scores[-3:]) / 7 if rpe_scores else 1.0
        )
        score = ExercisePrescription._comprehensive_deload_assessment(
            1 - perf_factor,
            rpe_factor,
            ac_ratio,
            rec_quality,
            0,
        )
        return {
            "trigger": round(trigger, 2),
            "score": round(score, 2),
        }

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
            self.settings.get_float("months_active", 1.0) if self.settings else 1.0
        )
        workouts_per_month = float(len(set(times)))
        body_weight = self._current_body_weight()

        base = ExerciseProgressEstimator.predict_progress(
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

        if self.progress_model is None:
            return base

        if (
            self.settings is not None
            and self.settings.get_bool("ml_all_enabled", True)
            and self.settings.get_bool("ml_training_enabled", True)
            and self.settings.get_bool("ml_progress_training_enabled", True)
        ):
            for idx, (r, w) in enumerate(zip(reps, weights)):
                rm = MathTools.epley_1rm(w, r)
                self.progress_model.train(float(idx), rm)

        last_idx = len(reps) - 1
        est_hist = [MathTools.epley_1rm(w, r) for w, r in zip(weights, reps)]
        slope = ExercisePrescription._linear_regression_slope(times, est_hist)
        lower, upper = ExercisePrescription._confidence_interval(slope, est_hist, times)
        result: List[Dict[str, float]] = []
        for item in base:
            t_idx = last_idx + item["week"] * workouts_per_week
            ml_pred = item["est_1rm"]
            if (
                self.settings is not None
                and self.settings.get_bool("ml_all_enabled", True)
                and self.settings.get_bool("ml_prediction_enabled", True)
                and self.settings.get_bool("ml_progress_prediction_enabled", True)
            ):
                ml_pred = self.progress_model.predict(float(t_idx))
            est = (item["est_1rm"] + ml_pred) / 2
            lo = est + lower * item["week"] * workouts_per_week
            hi = est + upper * item["week"] * workouts_per_week
            result.append(
                {
                    "week": item["week"],
                    "est_1rm": round(est, 2),
                    "lower": round(lo, 2),
                    "upper": round(hi, 2),
                }
            )

        return result

    def goal_progress(self, goal_id: int) -> List[Dict[str, float]]:
        """Return progress percentage for the specified goal."""
        if self.goals is None:
            return []
        goal = self.goals.fetch(goal_id)
        hist = self.progression(goal["exercise_name"], goal["start_date"])
        target = float(goal["target_value"])
        result: List[Dict[str, float]] = []
        for item in hist:
            pct = 0.0
            if target > 0:
                pct = (item["est_1rm"] / target) * 100.0
            result.append({"date": item["date"], "progress": round(pct, 2)})
        return result

    def equipment_usage(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """Return volume and set count per equipment."""
        names = self._all_names()
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
            if (
                self.settings is not None
                and self.settings.get_bool("hide_preconfigured_equipment", False)
                and self.equipment is not None
            ):
                detail = self.equipment.fetch_detail(eq_name)
                if detail is not None and detail[2] == 0:
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

    def recent_equipment(self, limit: int = 5) -> list[str]:
        """Return a list of recently used equipment names."""
        return self.sets.recent_equipment(limit)

    def recent_muscles(self, limit: int = 5) -> list[str]:
        """Return a list of muscles used with most recent equipment."""
        if self.equipment is None:
            return []
        eq_names = self.sets.recent_equipment(limit * 3)
        muscles: list[str] = []
        for eq in eq_names:
            for m in self.equipment.fetch_muscles(eq):
                if m not in muscles:
                    muscles.append(m)
                if len(muscles) >= limit:
                    return muscles[:limit]
        return muscles[:limit]

    def muscle_usage(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """Return volume and set count per muscle based on equipment."""
        if self.equipment is None:
            return []
        names = self._all_names()
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
            if (
                self.settings is not None
                and self.settings.get_bool("hide_preconfigured_equipment", False)
                and self.equipment is not None
            ):
                detail = self.equipment.fetch_detail(eq_name)
                if detail is not None and detail[2] == 0:
                    continue
            muscles = self.equipment.fetch_muscles(eq_name)
            for m in muscles:
                item = stats.setdefault(m, {"volume": 0.0, "sets": 0})
                item["volume"] += int(reps) * float(weight)
                item["sets"] += 1
        result = []
        for mus in sorted(stats):
            data = stats[mus]
            result.append(
                {
                    "muscle": mus,
                    "volume": round(data["volume"], 2),
                    "sets": data["sets"],
                }
            )
        return result

    def muscle_group_usage(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """Return volume and set count per muscle group."""
        if self.catalog is None:
            return []
        names = self._all_names()
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
            with_equipment=True,
        )
        stats: Dict[str, Dict[str, float]] = {}
        for reps, weight, _rpe, _date, ex_name, _eq in rows:
            canonical = self.exercise_names.canonical(ex_name)
            detail = self.catalog.fetch_detail(canonical)
            if detail is None:
                continue
            group = detail[0]
            item = stats.setdefault(group, {"volume": 0.0, "sets": 0})
            item["volume"] += int(reps) * float(weight)
            item["sets"] += 1
        result = []
        for group in sorted(stats):
            data = stats[group]
            result.append(
                {
                    "muscle_group": group,
                    "volume": round(data["volume"], 2),
                    "sets": data["sets"],
                }
            )
        return result

    def muscle_engagement_3d(
        self, start_date: str | None = None, end_date: str | None = None
    ) -> List[Dict[str, float]]:
        """Return muscle engagement metrics for 3D visualisation."""
        usage = self.muscle_usage(start_date, end_date)
        result = []
        for item in usage:
            sets = item["sets"]
            vol = item["volume"]
            intensity = vol / sets if sets else 0.0
            result.append(
                {
                    "muscle": item["muscle"],
                    "sets": sets,
                    "volume": vol,
                    "intensity": round(intensity, 2),
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

    def intensity_distribution(
        self,
        exercise: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float | int]]:
        """Return training volume and set count per intensity zone."""
        names = self._alias_names(exercise)
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
        )
        bins = [(i / 10.0, (i + 1) / 10.0) for i in range(10)]
        bins.append((1.0, 2.0))
        stats = {
            f"{int(lo*100)}-{int(hi*100 if hi < 1.0 else 100)}": {
                "sets": 0,
                "volume": 0.0,
            }
            for lo, hi in bins
        }
        for reps, weight, _rpe, _date in rows:
            est_rm = MathTools.epley_1rm(float(weight), int(reps))
            if est_rm <= 0:
                continue
            ratio = float(weight) / est_rm
            for lo, hi in bins:
                if lo <= ratio < hi:
                    key = f"{int(lo*100)}-{int(hi*100 if hi < 1.0 else 100)}"
                    entry = stats[key]
                    entry["sets"] += 1
                    entry["volume"] += int(reps) * float(weight)
                    break
        result = []
        for lo, hi in bins:
            key = f"{int(lo*100)}-{int(hi*100 if hi < 1.0 else 100)}"
            entry = stats[key]
            result.append(
                {
                    "zone": key,
                    "sets": entry["sets"],
                    "volume": round(entry["volume"], 2),
                }
            )
        return result

    def intensity_map(
        self,
        exercise: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float | int | str]]:
        """Return intensity distribution with color codes."""
        base = self.intensity_distribution(exercise, start_date, end_date)
        colors = [
            "#1a9641",
            "#a6d96a",
            "#ffffbf",
            "#fdae61",
            "#d7191c",
            "#800026",
        ]
        result: List[Dict[str, float | int | str]] = []
        for idx, entry in enumerate(base):
            color = colors[min(idx // 2, len(colors) - 1)]
            entry["color"] = color
            result.append(entry)
        return result

    def velocity_history(
        self,
        exercise: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """Return average set velocity per day for ``exercise``."""
        names = self._alias_names(exercise)
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
            with_duration=True,
        )
        by_date: Dict[str, List[float]] = {}
        for reps, _weight, _rpe, date, start, end in rows:
            vel = MathTools.estimate_velocity_from_set(int(reps), start, end)
            by_date.setdefault(date, []).append(vel)
        result: List[Dict[str, float]] = []
        for d in sorted(by_date):
            vals = by_date[d]
            avg = sum(vals) / len(vals) if vals else 0.0
            result.append({"date": d, "velocity": round(avg, 2)})
        return result

    def power_history(
        self,
        exercise: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """Return average power per day for ``exercise``."""
        names = self._alias_names(exercise)
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
            with_duration=True,
        )
        by_date: Dict[str, List[float]] = {}
        for reps, weight, _rpe, date, start, end in rows:
            power = MathTools.estimate_power_from_set(
                int(reps), float(weight), start, end
            )
            by_date.setdefault(date, []).append(power)
        result: List[Dict[str, float]] = []
        for d in sorted(by_date):
            vals = by_date[d]
            avg = sum(vals) / len(vals) if vals else 0.0
            result.append({"date": d, "power": round(avg, 2)})
        return result

    def relative_power_history(
        self,
        exercise: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """Return average power to body weight ratio per day."""
        body_weight = self._current_body_weight()
        if body_weight <= 0:
            return []
        names = self._alias_names(exercise)
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
            with_duration=True,
        )
        by_date: Dict[str, List[float]] = {}
        for reps, weight, _rpe, date, start, end in rows:
            power = MathTools.estimate_power_from_set(
                int(reps), float(weight), start, end
            )
            by_date.setdefault(date, []).append(power / body_weight)
        result: List[Dict[str, float]] = []
        for d in sorted(by_date):
            vals = by_date[d]
            avg = sum(vals) / len(vals) if vals else 0.0
            result.append({"date": d, "relative_power": round(avg, 2)})
        return result

    def overview(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, float]:
        """Return aggregated workout statistics."""
        names = self._all_names()
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
            with_equipment=True,
            with_duration=True,
            with_workout_id=True,
        )
        if not rows:
            return {"workouts": 0, "volume": 0.0, "avg_rpe": 0.0, "exercises": 0}
        workout_ids = set()
        exercises = set()
        volume = 0.0
        rpe_total = 0.0
        durations: Dict[int, float] = {}
        for reps, weight, rpe, _date, ex_name, _eq, start, end, wid in rows:
            workout_ids.add(wid)
            exercises.add(ex_name)
            volume += int(reps) * float(weight)
            rpe_total += int(rpe)
            if start and end:
                t0 = self._parse_timestamp(start)
                t1 = self._parse_timestamp(end)
                durations[wid] = durations.get(wid, 0.0) + (t1 - t0).total_seconds()
        avg_rpe = rpe_total / len(rows)
        total_duration = sum(durations.values())
        avg_density = MathTools.session_density(volume, total_duration)
        return {
            "workouts": len(workout_ids),
            "volume": round(volume, 2),
            "avg_rpe": round(avg_rpe, 2),
            "exercises": len(exercises),
            "avg_density": round(avg_density, 2),
        }

    def personal_records(
        self,
        exercise: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """Return the best set for each exercise based on estimated 1RM."""
        names = self._alias_names(exercise)
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
            with_equipment=True,
        )
        records: Dict[str, Dict[str, float]] = {}
        for reps, weight, rpe, date, ex_name, eq_name in rows:
            est = MathTools.epley_1rm(float(weight), int(reps))
            current = records.get(ex_name)
            if current is None or est > current["est_1rm"]:
                records[ex_name] = {
                    "exercise": ex_name,
                    "date": date,
                    "equipment": eq_name,
                    "reps": int(reps),
                    "weight": float(weight),
                    "rpe": int(rpe),
                    "est_1rm": round(est, 2),
                }
        return sorted(records.values(), key=lambda x: x["exercise"])

    def previous_personal_record(
        self, exercise: str, before_date: str
    ) -> Optional[Dict[str, float]]:
        """Return the best set before ``before_date``."""
        recs = self.personal_records(
            exercise=exercise,
            end_date=(datetime.date.fromisoformat(before_date) - datetime.timedelta(days=1)).isoformat(),
        )
        return recs[0] if recs else None

    def progress_insights(
        self,
        exercise: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, float]:
        """Return trend analysis and plateau score for an exercise."""
        prog = self.progression(exercise, start_date, end_date)
        if not prog:
            return {}
        dates = [datetime.date.fromisoformat(p["date"]) for p in prog]
        first = dates[0]
        ts = [(d - first).days for d in dates]
        rms = [float(p["est_1rm"]) for p in prog]
        trend = ExercisePrescription._analyze_1rm_trends(ts, rms)
        plateau = ExercisePrescription._pyramid_plateau_detection(ts, rms)
        trend["plateau_score"] = round(plateau, 2)
        return trend

    def plateau_score(
        self,
        exercise: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, float]:
        """Return advanced plateau score for ``exercise``."""
        names = self._alias_names(exercise)
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
        )
        if len(rows) < 6:
            return {"score": 0.0}
        weights = [float(r[1]) for r in rows]
        reps = [int(r[0]) for r in rows]
        rpes = [int(r[2]) for r in rows]
        dates = [r[3] for r in rows]
        base = datetime.date.fromisoformat(dates[0])
        times = [(datetime.date.fromisoformat(d) - base).days for d in dates]
        perf = [MathTools.epley_1rm(w, r) for w, r in zip(weights, reps)]
        vols = [w * r for w, r in zip(weights, reps)]
        score = ExercisePrescription._advanced_plateau_detection(
            perf, times, rpes, vols
        )
        return {"score": round(score, 2)}

    def training_stress(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """Return daily training stress and cumulative fatigue values."""
        names = self._all_names()
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
            with_duration=True,
        )
        if not rows:
            return []

        weights: List[float] = []
        reps: List[int] = []
        durs: List[float] = []
        dates: List[str] = []
        for r, w, _rpe, date, start, end in rows:
            weights.append(float(w))
            reps.append(int(r))
            if start and end:
                t0 = self._parse_timestamp(start)
                t1 = self._parse_timestamp(end)
                durs.append((t1 - t0).total_seconds())
            else:
                durs.append(50.0)
            dates.append(date)

        uniq_dates = sorted(set(dates))
        first = datetime.date.fromisoformat(dates[0])
        ts_all = [(datetime.date.fromisoformat(d) - first).days for d in dates]

        stress_map: Dict[str, float] = {d: 0.0 for d in uniq_dates}
        for d, w, r, dur in zip(dates, weights, reps, durs):
            rm = MathTools.epley_1rm(w, r)
            val = ExercisePrescription._calculate_exercise_tss([w], [r], [dur], rm)
            stress_map[d] += val

        results: List[Dict[str, float]] = []
        w_seen: List[float] = []
        r_seen: List[int] = []
        ts_seen: List[float] = []
        dur_seen: List[float] = []
        idx = 0
        for d in uniq_dates:
            while idx < len(dates) and dates[idx] == d:
                w_seen.append(weights[idx])
                r_seen.append(reps[idx])
                ts_seen.append(ts_all[idx])
                dur_seen.append(durs[idx])
                idx += 1
            current_rm = max(
                [MathTools.epley_1rm(w, r) for w, r in zip(w_seen, r_seen)]
            )
            fatigue = ExercisePrescription._tss_adjusted_fatigue(
                w_seen,
                r_seen,
                ts_seen,
                dur_seen,
                current_rm,
            )
            results.append(
                {
                    "date": d,
                    "stress": round(stress_map[d], 2),
                    "fatigue": round(fatigue, 2),
                }
            )

        results.sort(key=lambda x: x["date"])
        return results

    def weekly_load_variability(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, object]:
        names = self._all_names()
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
        )
        if not rows:
            return {"variability": 0.0, "weeks": [], "volumes": []}

        base = datetime.date.fromisoformat(rows[0][3])
        weights: List[float] = []
        reps: List[int] = []
        times: List[float] = []
        for r, w, _rpe, date in rows:
            weights.append(float(w))
            reps.append(int(r))
            days = (datetime.date.fromisoformat(date) - base).days
            times.append(float(days))

        variability = ExercisePrescription._weekly_load_variability(
            weights, reps, times
        )
        vols: Dict[int, float] = {}
        for w, r, t in zip(weights, reps, times):
            week = int(t // 7)
            vols[week] = vols.get(week, 0.0) + w * r
        weeks_sorted = sorted(vols)
        week_labels = [
            (base + datetime.timedelta(days=w * 7)).isoformat() for w in weeks_sorted
        ]
        volumes = [round(vols[w], 2) for w in weeks_sorted]
        return {
            "variability": round(variability, 2),
            "weeks": week_labels,
            "volumes": volumes,
        }

    def training_monotony(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, float]:
        """Return training monotony value across the specified dates."""
        names = self._all_names()
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
        )
        if not rows:
            return {"monotony": 1.0}

        weights = [float(r[1]) for r in rows]
        reps = [int(r[0]) for r in rows]
        val = ExercisePrescription._weekly_monotony(weights, reps)
        return {"monotony": round(val, 2)}

    def training_strain(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """Return weekly training strain values."""
        variability = self.weekly_load_variability(start_date, end_date)
        if not variability["weeks"]:
            return []
        monotony = self.training_monotony(start_date, end_date)["monotony"]
        var = variability["variability"]
        strain: List[Dict[str, float]] = []
        for week, volume in zip(variability["weeks"], variability["volumes"]):
            score = float(volume) * monotony * (1 + var / 10.0)
            strain.append({"week": week, "strain": round(score, 2)})
        return strain

    def weekly_volume_change(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """Return week-over-week volume percentage change."""
        variability = self.weekly_load_variability(start_date, end_date)
        weeks = variability["weeks"]
        volumes = variability["volumes"]
        if len(volumes) < 2:
            return []
        result: List[Dict[str, float]] = []
        for idx in range(1, len(volumes)):
            prev = volumes[idx - 1]
            change = 0.0 if prev == 0 else (volumes[idx] - prev) / prev * 100.0
            result.append({"week": weeks[idx], "change": round(change, 2)})
        return result

    def stress_balance(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """Return Training Stress Balance across dates."""
        names = self._all_names()
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
            with_duration=True,
        )
        if not rows:
            return []
        weights: List[float] = []
        reps: List[int] = []
        durations: List[float] = []
        dates: List[str] = []
        for r, w, _rpe, date, start, end in rows:
            weights.append(float(w))
            reps.append(int(r))
            if start and end:
                t0 = self._parse_timestamp(start)
                t1 = self._parse_timestamp(end)
                durations.append((t1 - t0).total_seconds())
            else:
                durations.append(50.0)
            dates.append(date)
        base = datetime.date.fromisoformat(dates[0])
        times = [(datetime.date.fromisoformat(d) - base).days for d in dates]
        current_rm = ExercisePrescription._current_1rm(weights, reps)
        days, tsb = ExercisePrescription._training_stress_balance(
            weights,
            reps,
            durations,
            times,
            current_rm,
        )
        result: List[Dict[str, float]] = []
        for d, v in zip(days, tsb):
            result.append(
                {
                    "date": (base + datetime.timedelta(days=d)).isoformat(),
                    "tsb": round(v, 2),
                }
            )
        result.sort(key=lambda x: x["date"])
        return result

    def session_efficiency(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """Return efficiency score per workout."""
        names = self._all_names()
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
            with_duration=True,
            with_workout_id=True,
        )
        if not rows:
            return []
        by_workout: Dict[int, Dict[str, object]] = {}
        for r, w, rpe, date, start, end, wid in rows:
            entry = by_workout.setdefault(
                wid,
                {"date": date, "volume": 0.0, "dur": 0.0, "rpe": []},
            )
            entry["volume"] += int(r) * float(w)
            if start and end:
                t0 = self._parse_timestamp(start)
                t1 = self._parse_timestamp(end)
                entry["dur"] += (t1 - t0).total_seconds()
            entry["rpe"].append(int(rpe))
        result: List[Dict[str, float]] = []
        for wid, data in sorted(by_workout.items()):
            duration = float(data["dur"])
            avg_rpe = sum(data["rpe"]) / len(data["rpe"]) if data["rpe"] else None
            eff = MathTools.session_efficiency(data["volume"], duration, avg_rpe)
            result.append(
                {
                    "workout_id": wid,
                    "date": data["date"],
                    "efficiency": round(eff, 2),
                }
            )
        return result

    def session_density(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """Return volume per minute for each workout."""
        names = self._all_names()
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
            with_duration=True,
            with_workout_id=True,
        )
        if not rows:
            return []
        by_workout: Dict[int, Dict[str, object]] = {}
        for r, w, _rpe, date, start, end, wid in rows:
            entry = by_workout.setdefault(
                wid, {"date": date, "volume": 0.0, "dur": 0.0}
            )
            entry["volume"] += int(r) * float(w)
            if start and end:
                t0 = self._parse_timestamp(start)
                t1 = self._parse_timestamp(end)
                entry["dur"] += (t1 - t0).total_seconds()
        result: List[Dict[str, float]] = []
        for wid, data in sorted(by_workout.items()):
            density = MathTools.session_density(data["volume"], float(data["dur"]))
            result.append(
                {"workout_id": wid, "date": data["date"], "density": round(density, 2)}
            )
        return result

    def set_pace(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """Return sets per minute for each workout."""
        names = self._all_names()
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
            with_duration=True,
            with_workout_id=True,
        )
        if not rows:
            return []
        by_workout: Dict[int, Dict[str, object]] = {}
        for _r, _w, _rpe, date, start, end, wid in rows:
            entry = by_workout.setdefault(wid, {"date": date, "sets": 0, "dur": 0.0})
            entry["sets"] += 1
            if start and end:
                t0 = self._parse_timestamp(start)
                t1 = self._parse_timestamp(end)
                entry["dur"] += (t1 - t0).total_seconds()
        result: List[Dict[str, float]] = []
        for wid, data in sorted(by_workout.items()):
            pace = MathTools.set_pace(int(data["sets"]), float(data["dur"]))
            result.append(
                {"workout_id": wid, "date": data["date"], "pace": round(pace, 2)}
            )
        return result

    def rest_times(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """Return average rest duration between sets per workout."""
        names = self._all_names()
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
            with_duration=True,
            with_workout_id=True,
        )
        if not rows:
            return []
        by_workout: Dict[int, List[Tuple[str, str]]] = {}
        for _r, _w, _rpe, _date, start, end, wid in rows:
            if start and end:
                by_workout.setdefault(wid, []).append((start, end))
        result: List[Dict[str, float]] = []
        for wid, times in sorted(by_workout.items()):
            times_sorted = sorted(times, key=lambda t: t[0])
            rests: List[float] = []
            for i in range(1, len(times_sorted)):
                prev_end = self._parse_timestamp(times_sorted[i - 1][1])
                curr_start = self._parse_timestamp(times_sorted[i][0])
                diff = (curr_start - prev_end).total_seconds()
                if diff > 0:
                    rests.append(diff)
            avg = sum(rests) / len(rests) if rests else 0.0
            result.append({"workout_id": wid, "avg_rest": round(avg, 2)})
        return result

    def volume_heatmap(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """Return weekly training volume for heatmap charts."""
        names = self._all_names()
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
        )
        by_week: Dict[str, float] = {}
        for reps, weight, _rpe, date in rows:
            d = datetime.date.fromisoformat(date)
            key = f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}"
            by_week[key] = by_week.get(key, 0.0) + int(reps) * float(weight)
        result: List[Dict[str, float]] = []
        for week in sorted(by_week):
            result.append({"week": week, "volume": round(by_week[week], 2)})
        return result

    def session_duration(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """Return total duration between first set start and last set finish."""
        names = self._all_names()
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
            with_duration=True,
            with_workout_id=True,
        )
        if not rows:
            return []
        by_workout: Dict[int, Dict[str, str]] = {}
        for _r, _w, _rpe, date, start, end, wid in rows:
            if not start or not end:
                continue
            entry = by_workout.setdefault(
                wid, {"date": date, "start": start, "end": end}
            )
            if start < entry["start"]:
                entry["start"] = start
            if end > entry["end"]:
                entry["end"] = end
        result: List[Dict[str, float]] = []
        for wid, data in sorted(by_workout.items()):
            t0 = self._parse_timestamp(data["start"])
            t1 = self._parse_timestamp(data["end"])
            dur = (t1 - t0).total_seconds()
            result.append(
                {
                    "workout_id": wid,
                    "date": data["date"],
                    "duration": round(dur, 2),
                }
            )
        return result

    def time_under_tension(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """Return total time under tension per workout."""
        names = self._all_names()
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
            with_duration=True,
            with_workout_id=True,
        )
        if not rows:
            return []
        by_workout: Dict[int, Dict[str, float | str]] = {}
        for _r, _w, _rpe, date, start, end, wid in rows:
            if not start or not end:
                continue
            t0 = self._parse_timestamp(start)
            t1 = self._parse_timestamp(end)
            dur = (t1 - t0).total_seconds()
            entry = by_workout.setdefault(wid, {"date": date, "tut": 0.0})
            entry["tut"] += dur
        result: List[Dict[str, float]] = []
        for wid, data in sorted(by_workout.items()):
            result.append(
                {
                    "workout_id": wid,
                    "date": str(data["date"]),
                    "tut": round(float(data["tut"]), 2),
                }
            )
        return result

    def exercise_diversity(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """Return exercise diversity score per workout."""
        names = self._all_names()
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
            with_equipment=True,
            with_workout_id=True,
        )
        if not rows:
            return []
        by_workout: Dict[int, Dict[str, object]] = {}
        for _r, _w, _rpe, date, ex_name, _eq, wid in rows:
            entry = by_workout.setdefault(wid, {"date": date, "counts": {}})
            counts = entry["counts"]
            counts[ex_name] = counts.get(ex_name, 0) + 1
        result: List[Dict[str, float]] = []
        for wid in sorted(by_workout):
            data = by_workout[wid]
            counts = data["counts"].values()
            div = MathTools.diversity_index(counts)
            result.append(
                {
                    "workout_id": wid,
                    "date": data["date"],
                    "diversity": round(div, 2),
                }
            )
        return result

    def location_summary(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float | int]]:
        """Return workout counts and volume grouped by location."""
        names = self._all_names()
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
            with_workout_id=True,
            with_location=True,
        )
        if not rows:
            return []
        stats: Dict[str, Dict[str, object]] = {}
        for reps, weight, _rpe, _date, wid, location in rows:
            loc = location or ""
            entry = stats.setdefault(loc, {"volume": 0.0, "workouts": set()})
            entry["volume"] += int(reps) * float(weight)
            entry["workouts"].add(wid)
        result: List[Dict[str, float | int]] = []
        for loc in sorted(stats):
            entry = stats[loc]
            result.append(
                {
                    "location": loc,
                    "workouts": len(entry["workouts"]),
                    "volume": round(entry["volume"], 2),
                }
            )
        return result

    def training_type_summary(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> List[Dict[str, float | int]]:
        """Return workout counts and volume grouped by training type."""
        if self.workouts is None:
            return []
        workouts = self.workouts.fetch_all_workouts(start_date, end_date)
        stats: Dict[str, Dict[str, float | int]] = {}
        for wid, _date, _s, _e, t_type, _notes, _rating, *_ in workouts:
            summary = self.sets.workout_summary(wid)
            entry = stats.setdefault(t_type, {"workouts": 0, "volume": 0.0, "sets": 0})
            entry["workouts"] += 1
            entry["volume"] += summary["volume"]
            entry["sets"] += summary["sets"]
        result: List[Dict[str, float | int]] = []
        for t_type in sorted(stats):
            entry = stats[t_type]
            result.append(
                {
                    "training_type": t_type,
                    "workouts": entry["workouts"],
                    "volume": round(float(entry["volume"]), 2),
                    "sets": entry["sets"],
                }
            )
        return result

    def stress_overview(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, float]:
        """Return overall stress and fatigue for the period."""
        names = self._all_names()
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
            with_duration=True,
        )
        if not rows:
            return {"stress": 0.0, "fatigue": 0.0}

        base = datetime.date.fromisoformat(rows[0][3])
        weights: List[float] = []
        reps: List[int] = []
        rpes: List[int] = []
        times: List[float] = []
        durations: List[float] = []
        for r, w, rpe, date, start, end in rows:
            weights.append(float(w))
            reps.append(int(r))
            rpes.append(int(rpe))
            times.append((datetime.date.fromisoformat(date) - base).days)
            if start and end:
                t0 = self._parse_timestamp(start)
                t1 = self._parse_timestamp(end)
                durations.append((t1 - t0).total_seconds())
            else:
                durations.append(50.0)

        current_rm = ExercisePrescription._current_1rm(weights, reps)
        stress = ExercisePrescription._stress_level(
            weights,
            reps,
            rpes,
            times,
            current_rm,
            10,
        )
        fatigue = ExercisePrescription._tss_adjusted_fatigue(
            weights,
            reps,
            times,
            durations,
            current_rm,
        )
        return {"stress": round(stress, 2), "fatigue": round(fatigue, 2)}

    def volume_forecast(
        self,
        days: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """Forecast daily training volume for upcoming days."""
        names = self._all_names()
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
        )
        if not rows:
            return []

        volumes: Dict[str, float] = {}
        for reps, weight, _rpe, date in rows:
            volumes[date] = volumes.get(date, 0.0) + int(reps) * float(weight)

        ordered_dates = sorted(volumes)
        base = datetime.date.fromisoformat(ordered_dates[0])
        hist = [volumes[d] for d in ordered_dates]
        ts_last = (datetime.date.fromisoformat(ordered_dates[-1]) - base).days

        vals = hist[:]
        result: List[Dict[str, float]] = []
        for i in range(days):
            next_arima = ExercisePrescription._arima_forecast(vals, steps=1)
            features = vals[-3:] if len(vals) >= 3 else ([vals[-1]] * 3)
            ml_pred = next_arima
            if (
                self.volume_model is not None
                and self.settings is not None
                and self.settings.get_bool("ml_all_enabled", True)
                and self.settings.get_bool("ml_prediction_enabled", True)
                and self.settings.get_bool("ml_volume_prediction_enabled", True)
            ):
                ml_pred = self.volume_model.predict(features, next_arima)
            next_val = (next_arima + ml_pred) / 2
            vals.append(next_val)
            day = base + datetime.timedelta(days=ts_last + i + 1)
            result.append({"date": day.isoformat(), "volume": round(next_val, 2)})

        return result

    def overtraining_risk(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, float]:
        """Return an overtraining risk score for the period."""
        overview = self.stress_overview(start_date, end_date)
        variability = self.weekly_load_variability(start_date, end_date)
        risk = MathTools.overtraining_index(
            overview["stress"],
            overview["fatigue"],
            variability["variability"],
        )
        return {"risk": round(risk, 2)}

    def injury_risk(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, float]:
        """Predict injury risk probability for the period."""
        overview = self.stress_overview(start_date, end_date)
        variability = self.weekly_load_variability(start_date, end_date)
        features = [overview["stress"], overview["fatigue"], variability["variability"]]
        base = MathTools.clamp(sum(features) / 3.0, 0.0, 10.0) / 10.0
        risk = base
        if (
            self.injury_model is not None
            and self.settings is not None
            and self.settings.get_bool("ml_all_enabled", True)
            and self.settings.get_bool("ml_prediction_enabled", True)
            and self.settings.get_bool("ml_injury_prediction_enabled", True)
        ):
            risk = self.injury_model.predict(features)
        if (
            self.injury_model is not None
            and self.settings is not None
            and self.settings.get_bool("ml_all_enabled", True)
            and self.settings.get_bool("ml_training_enabled", True)
            and self.settings.get_bool("ml_injury_training_enabled", True)
        ):
            self.injury_model.train(features, base)
        return {"injury_risk": round(risk, 2)}

    def readiness(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """Return daily readiness scores."""
        names = self._all_names()
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
            with_duration=True,
        )
        if not rows:
            return []
        by_date: Dict[str, Dict[str, list]] = {}
        for r, w, rpe, date, start, end in rows:
            entry = by_date.setdefault(date, {"w": [], "r": [], "rpe": [], "d": []})
            entry["w"].append(float(w))
            entry["r"].append(int(r))
            entry["rpe"].append(int(rpe))
            if start and end:
                t0 = self._parse_timestamp(start)
                t1 = self._parse_timestamp(end)
                entry["d"].append((t1 - t0).total_seconds())
            else:
                entry["d"].append(50.0)
        result: List[Dict[str, float]] = []
        for d in sorted(by_date):
            data = by_date[d]
            current_rm = ExercisePrescription._current_1rm(data["w"], data["r"])
            stress = ExercisePrescription._stress_level(
                data["w"],
                data["r"],
                data["rpe"],
                list(range(len(data["w"]))),
                current_rm,
                10,
            )
            fatigue = ExercisePrescription._tss_adjusted_fatigue(
                data["w"], data["r"], list(range(len(data["w"]))), data["d"], current_rm
            )
            base_ready = MathTools.readiness_score(stress, fatigue / 1000)
            ready_val = base_ready
            if (
                self.readiness_model is not None
                and self.settings is not None
                and self.settings.get_bool("ml_all_enabled", True)
                and self.settings.get_bool("ml_prediction_enabled", True)
                and self.settings.get_bool("ml_readiness_prediction_enabled", True)
            ):
                ready_val = self.readiness_model.predict(stress, fatigue, base_ready)
            if (
                self.readiness_model is not None
                and self.settings is not None
                and self.settings.get_bool("ml_all_enabled", True)
                and self.settings.get_bool("ml_training_enabled", True)
                and self.settings.get_bool("ml_readiness_training_enabled", True)
            ):
                self.readiness_model.train(stress, fatigue, base_ready)
        result.append({"date": d, "readiness": round(ready_val, 2)})
        return result

    def readiness_stats(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> Dict[str, float]:
        """Return average, min and max readiness for the period."""
        history = self.readiness(start_date, end_date)
        if not history:
            return {"avg": 0.0, "min": 0.0, "max": 0.0}
        vals = [h["readiness"] for h in history]
        return {
            "avg": round(sum(vals) / len(vals), 2),
            "min": min(vals),
            "max": max(vals),
        }

    def performance_momentum(
        self,
        exercise: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, float]:
        """Return a momentum score based on 1RM progression for ``exercise``."""
        names = self._alias_names(exercise)
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
        )
        if not rows:
            return {"momentum": 0.0}

        base = datetime.date.fromisoformat(rows[0][3])
        times: list[int] = []
        ests: list[float] = []
        for reps, weight, _rpe, date in rows:
            times.append((datetime.date.fromisoformat(date) - base).days)
            ests.append(MathTools.epley_1rm(float(weight), int(reps)))

        slope = ExercisePrescription._weighted_slope(times, ests, alpha=0.4)
        change = ExercisePrescription._change_point(ests, times)
        low, mid, high = ExercisePrescription._wavelet_energy(ests)
        energy = high / (low + mid + ExercisePrescription.EPSILON)
        momentum = slope * (1 + change / len(ests)) * (1 + energy / 10)
        return {"momentum": round(momentum, 4)}

    def adaptation_index(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, float]:
        """Return a multi-modal adaptation score."""
        overview = self.stress_overview(start_date, end_date)
        variability = self.weekly_load_variability(start_date, end_date)
        monotony = self.training_monotony(start_date, end_date)
        features = [
            MathTools.clamp(overview["stress"] / 10.0, 0.0, 1.0),
            MathTools.clamp(overview["fatigue"] / 10.0, 0.0, 1.0),
            MathTools.clamp(variability["variability"] / 10.0, 0.0, 1.0),
            MathTools.clamp(monotony["monotony"] / 10.0, 0.0, 1.0),
            0.5,
        ]
        base = sum(features) / len(features)
        score = base
        if (
            self.adaptation_model is not None
            and self.settings is not None
            and self.settings.get_bool("ml_all_enabled", True)
            and self.settings.get_bool("ml_prediction_enabled", True)
            and self.settings.get_bool("experimental_models_enabled", False)
        ):
            score = self.adaptation_model.predict(features, base)
        if (
            self.adaptation_model is not None
            and self.settings is not None
            and self.settings.get_bool("ml_all_enabled", True)
            and self.settings.get_bool("ml_training_enabled", True)
            and self.settings.get_bool("experimental_models_enabled", False)
        ):
            self.adaptation_model.train(features, base)
        return {"adaptation": round(score * 10.0, 2)}

    def body_weight_history(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        unit: str = "kg",
    ) -> List[Dict[str, float]]:
        if self.body_weights is None:
            return []
        rows = self.body_weights.fetch_history(start_date, end_date)
        factor = 2.20462 if unit == "lb" else 1.0
        return [
            {"id": rid, "date": d, "weight": round(w * factor, 2)} for rid, d, w in rows
        ]

    def weight_stats(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        unit: str = "kg",
    ) -> Dict[str, float]:
        key = (start_date, end_date, unit)
        if self.stats_cache is not None:
            cached = self.stats_cache.fetch_weight_stats(start_date, end_date, unit)
            if cached is not None:
                self._cache[key] = cached
                return cached
        if key in self._cache:
            return self._cache[key]
        history = self.body_weight_history(start_date, end_date, unit)
        if not history:
            result = {"avg": 0.0, "min": 0.0, "max": 0.0}
            self._cache[key] = result
            if self.stats_cache is not None:
                self.stats_cache.save_weight_stats(
                    start_date, end_date, unit, 0.0, 0.0, 0.0
                )
            return result
        weights = [h["weight"] for h in history]
        result = {
            "avg": round(sum(weights) / len(weights), 2),
            "min": min(weights),
            "max": max(weights),
        }
        self._cache[key] = result
        if self.stats_cache is not None:
            self.stats_cache.save_weight_stats(
                start_date,
                end_date,
                unit,
                result["avg"],
                result["min"],
                result["max"],
            )
        return result

    def rating_history(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> List[Dict[str, int]]:
        """Return workout ratings sorted by date."""
        if self.workouts is None:
            return []
        rows = self.workouts.fetch_ratings(start_date, end_date)
        return [{"date": d, "rating": r} for d, r in rows]

    def rating_stats(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> Dict[str, float]:
        history = self.rating_history(start_date, end_date)
        if not history:
            return {"avg": 0.0, "min": 0.0, "max": 0.0}
        ratings = [h["rating"] for h in history]
        return {
            "avg": round(sum(ratings) / len(ratings), 2),
            "min": min(ratings),
            "max": max(ratings),
        }

    def rating_distribution(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> List[Dict[str, int]]:
        if self.workouts is None:
            return []
        rows = self.workouts.fetch_ratings(start_date, end_date)
        dist: Dict[int, int] = {}
        for _d, rating in rows:
            key = int(rating)
            dist[key] = dist.get(key, 0) + 1
        return [{"rating": r, "count": dist[r]} for r in sorted(dist)]

    def workout_calories(self, workout_id: int) -> float:
        """Estimate calories burned for a workout."""
        if self.workouts is None:
            return 0.0
        summary = self.sets.workout_summary(workout_id)
        duration = self.workouts.workout_duration(workout_id)
        if duration is None:
            duration = summary["sets"] * 90
        weight = 80.0
        if self.settings is not None:
            weight = self.settings.get_float("body_weight", 80.0)
        cals = (summary["volume"] / weight) * 0.1
        cals += (duration / 60.0) * 6
        return round(cals, 2)

    def bmi(self) -> float:
        """Return current BMI using latest weight and height setting."""
        if self.settings is None:
            return 0.0
        weight = self._current_body_weight()
        height = self.settings.get_float("height", 1.75)
        if height <= 0:
            return 0.0
        return round(weight / (height**2), 2)

    def bmi_history(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> List[Dict[str, float]]:
        """Return BMI values for all logged body weight entries."""
        if self.body_weights is None or self.settings is None:
            return []
        height = self.settings.get_float("height", 1.75)
        if height <= 0:
            return []
        rows = self.body_weights.fetch_history(start_date, end_date)
        result: List[Dict[str, float]] = []
        for _rid, d, w in rows:
            result.append({"date": d, "bmi": round(w / (height**2), 2)})
        return result

    def weight_forecast(self, days: int) -> List[Dict[str, float]]:
        """Return simple body weight forecast for ``days`` ahead."""
        if days <= 0 or self.body_weights is None:
            return []
        history = self.body_weight_history()
        if len(history) < 2:
            last = history[-1]["weight"] if history else 0.0
            return [{"day": i, "weight": round(last, 2)} for i in range(1, days + 1)]
        weights = [h["weight"] for h in history]
        times = list(range(len(weights)))
        wts = [i + 1 for i in times]
        slope = ExercisePrescription._weighted_linear_regression(times, weights, wts)
        last = weights[-1]
        forecast: List[Dict[str, float]] = []
        for i in range(1, days + 1):
            forecast.append({"day": i, "weight": round(last + slope * i, 2)})
        return forecast

    def wellness_history(
        self, start_date: str | None = None, end_date: str | None = None
    ) -> List[Dict[str, float | int | None]]:
        if self.wellness is None:
            return []
        rows = self.wellness.fetch_history(start_date, end_date)
        result: List[Dict[str, float | int | None]] = []
        for rid, d, cal, sh, sq, stress in rows:
            result.append(
                {
                    "id": rid,
                    "date": d,
                    "calories": cal,
                    "sleep_hours": sh,
                    "sleep_quality": sq,
                    "stress_level": stress,
                }
            )
        return result

    def wellness_summary(
        self, start_date: str | None = None, end_date: str | None = None
    ) -> Dict[str, float]:
        history = self.wellness_history(start_date, end_date)
        if not history:
            return {
                "avg_calories": 0.0,
                "avg_sleep": 0.0,
                "avg_quality": 0.0,
                "avg_stress": 0.0,
            }
        cals = [h["calories"] for h in history if h["calories"] is not None]
        sleeps = [h["sleep_hours"] for h in history if h["sleep_hours"] is not None]
        quals = [h["sleep_quality"] for h in history if h["sleep_quality"] is not None]
        stress = [h["stress_level"] for h in history if h["stress_level"] is not None]
        return {
            "avg_calories": round(sum(cals) / len(cals), 2) if cals else 0.0,
            "avg_sleep": round(sum(sleeps) / len(sleeps), 2) if sleeps else 0.0,
            "avg_quality": round(sum(quals) / len(quals), 2) if quals else 0.0,
            "avg_stress": round(sum(stress) / len(stress), 2) if stress else 0.0,
        }

    def heart_rate_history(
        self, start_date: str | None = None, end_date: str | None = None
    ) -> list[dict[str, int | str]]:
        """Return logged heart rate entries ordered by timestamp."""
        if self.heart_rates is None:
            return []
        rows = self.heart_rates.fetch_range(start_date, end_date)
        return [
            {
                "id": rid,
                "workout_id": wid,
                "timestamp": ts,
                "heart_rate": hr,
            }
            for rid, wid, ts, hr in rows
        ]

    def heart_rate_summary(
        self, start_date: str | None = None, end_date: str | None = None
    ) -> dict[str, float]:
        """Return average, min and max heart rate for the range."""
        history = self.heart_rate_history(start_date, end_date)
        if not history:
            return {"avg": 0.0, "min": 0.0, "max": 0.0}
        rates = [h["heart_rate"] for h in history]
        return {
            "avg": round(sum(rates) / len(rates), 2),
            "min": float(min(rates)),
            "max": float(max(rates)),
        }

    def heart_rate_zones(
        self, start_date: str | None = None, end_date: str | None = None
    ) -> list[dict[str, float]]:
        """Return distribution of heart rate measurements across intensity zones."""
        history = self.heart_rate_history(start_date, end_date)
        if not history:
            return []
        max_hr = max(h["heart_rate"] for h in history)
        boundaries = [0.6, 0.7, 0.8, 0.9]
        zones = []
        last = 0.0
        for b in boundaries:
            zones.append((last, b))
            last = b
        zones.append((last, 1.01))
        total = len(history)
        result: list[dict[str, float]] = []
        for idx, (lo, hi) in enumerate(zones, start=1):
            lo_val = lo * max_hr
            hi_val = hi * max_hr
            count = sum(1 for h in history if lo_val <= h["heart_rate"] < hi_val)
            percent = count / total * 100.0 if total else 0.0
            result.append(
                {
                    "zone": str(idx),
                    "count": count,
                    "percent": round(percent, 2),
                }
            )
        return result

    def exercise_frequency(
        self,
        exercise: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, float]]:
        """Return weekly exercise frequency for each exercise."""
        names = self._alias_names(exercise)
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
            with_equipment=True,
        )
        if not rows:
            return []

        by_name: dict[str, set[str]] = {}
        all_dates: set[str] = set()
        for _r, _w, _rpe, date, ex_name, _eq in rows:
            canonical = self.exercise_names.canonical(ex_name)
            by_name.setdefault(canonical, set()).add(date)
            all_dates.add(date)

        if start_date is None:
            start_date = min(all_dates)
        if end_date is None:
            end_date = max(all_dates)

        start = datetime.date.fromisoformat(start_date)
        end = datetime.date.fromisoformat(end_date)
        weeks = (end - start).days // 7 + 1
        result: list[dict[str, float]] = []
        for name in sorted(by_name):
            freq = len(by_name[name]) / weeks if weeks > 0 else 0.0
            result.append({"exercise": name, "frequency_per_week": round(freq, 2)})
        return result

    def workout_consistency(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, float]:
        """Return coefficient of variation of workout intervals."""
        if self.workouts is None:
            return {"consistency": 0.0, "average_gap": 0.0}
        rows = self.workouts.fetch_all_workouts(start_date, end_date)
        dates = [datetime.date.fromisoformat(d) for _id, d, *_ in rows]
        if len(dates) < 2:
            return {"consistency": 0.0, "average_gap": 0.0}
        dates.sort()
        gaps = [(b - a).days for a, b in zip(dates[:-1], dates[1:])]
        avg_gap = sum(gaps) / len(gaps)
        cv = MathTools.coefficient_of_variation(gaps)
        return {"consistency": round(cv, 2), "average_gap": round(avg_gap, 2)}

    def weekly_streak(self) -> dict[str, int]:
        """Return current and best weekly workout streaks."""
        if self.workouts is None:
            return {"current": 0, "best": 0}
        rows = self.workouts.fetch_all("SELECT date FROM workouts ORDER BY date;")
        if not rows:
            return {"current": 0, "best": 0}
        weeks = sorted(
            {datetime.date.fromisoformat(d).isocalendar()[:2] for (d,) in rows}
        )
        best = cur = 1
        for prev, nxt in zip(weeks, weeks[1:]):
            if (nxt[0] == prev[0] and nxt[1] == prev[1] + 1) or (
                nxt[0] == prev[0] + 1 and prev[1] >= 52 and nxt[1] == 1
            ):
                cur += 1
            else:
                best = max(best, cur)
                cur = 1
        best = max(best, cur)
        current = 1
        for prev, nxt in zip(reversed(weeks[:-1]), reversed(weeks[1:])):
            if (nxt[0] == prev[0] and nxt[1] == prev[1] + 1) or (
                nxt[0] == prev[0] + 1 and prev[1] >= 52 and nxt[1] == 1
            ):
                current += 1
            else:
                break
        return {"current": current, "best": best}

    def moving_average_progress(
        self,
        exercise: str,
        window: int = 7,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, float]]:
        """Return moving average of estimated 1RM progression."""
        hist = self.progression(exercise, start_date, end_date)
        values = [h["est_1rm"] for h in hist]
        dates = [h["date"] for h in hist]
        result: list[dict[str, float]] = []
        for i, val in enumerate(values):
            start = max(0, i - window + 1)
            window_vals = values[start : i + 1]
            avg = sum(window_vals) / len(window_vals)
            result.append({"date": dates[i], "moving_avg": round(avg, 2)})
        return result

    def progression_chart_pdf(
        self,
        exercise: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> bytes:
        """Return a PDF line chart of 1RM progression."""
        data = self.progression(exercise, start_date, end_date)
        if not data:
            return b""
        import matplotlib.pyplot as plt
        from io import BytesIO

        dates = [d["date"] for d in data]
        values = [d["est_1rm"] for d in data]
        plt.figure()
        plt.plot(dates, values, marker="o")
        plt.title(f"{exercise} 1RM Progress")
        plt.xlabel("Date")
        plt.ylabel("Estimated 1RM")
        plt.tight_layout()
        buf = BytesIO()
        plt.savefig(buf, format="pdf")
        plt.close()
        return buf.getvalue()

    def compare_progress(
        self,
        exercise1: str,
        exercise2: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, float]]:
        """Return difference in estimated 1RM between two exercises."""
        p1 = {p["date"]: p["est_1rm"] for p in self.progression(exercise1, start_date, end_date)}
        p2 = {p["date"]: p["est_1rm"] for p in self.progression(exercise2, start_date, end_date)}
        dates = sorted(set(p1) & set(p2))
        result: list[dict[str, float]] = []
        for d in dates:
            result.append({"date": d, "difference": round(p1[d] - p2[d], 2)})
        return result

    def workout_summary_image(self, workout_id: int) -> bytes:
        """Return PNG image summarizing workout volume, sets and avg RPE."""
        summary = self.sets.workout_summary(workout_id)
        from io import BytesIO
        from PIL import Image, ImageDraw, ImageFont

        img = Image.new("RGB", (400, 160), "white")
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        draw.text((10, 10), f"Workout {workout_id}", fill="black", font=font)
        draw.text((10, 50), f"Volume: {summary['volume']} kg", fill="black", font=font)
        draw.text((10, 80), f"Sets: {summary['sets']}", fill="black", font=font)
        draw.text((10, 110), f"Avg RPE: {summary['avg_rpe']}", fill="black", font=font)
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
