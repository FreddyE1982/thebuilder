from __future__ import annotations
import datetime
from typing import List, Optional, Dict
from db import SetRepository, ExerciseNameRepository, SettingsRepository
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
    ) -> None:
        self.sets = set_repo
        self.exercise_names = name_repo
        self.settings = settings_repo
        self.volume_model = volume_model
        self.readiness_model = readiness_model
        self.progress_model = progress_model
        self.injury_model = injury_model
        self.adaptation_model = adaptation_model

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
                t0 = datetime.datetime.fromisoformat(start)
                t1 = datetime.datetime.fromisoformat(end)
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
        body_weight = (
            self.settings.get_float("body_weight", 80.0)
            if self.settings
            else 80.0
        )
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
            result.append({"week": item["week"], "est_1rm": round(est, 2)})

        return result

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

    def overview(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, float]:
        """Return aggregated workout statistics."""
        names = self.exercise_names.fetch_all()
        rows = self.sets.fetch_history_by_names(
            names,
            start_date=start_date,
            end_date=end_date,
            with_equipment=True,
            with_workout_id=True,
        )
        if not rows:
            return {"workouts": 0, "volume": 0.0, "avg_rpe": 0.0, "exercises": 0}
        workout_ids = set()
        exercises = set()
        volume = 0.0
        rpe_total = 0.0
        for reps, weight, rpe, _date, ex_name, _eq, wid in rows:
            workout_ids.add(wid)
            exercises.add(ex_name)
            volume += int(reps) * float(weight)
            rpe_total += int(rpe)
        avg_rpe = rpe_total / len(rows)
        return {
            "workouts": len(workout_ids),
            "volume": round(volume, 2),
            "avg_rpe": round(avg_rpe, 2),
            "exercises": len(exercises),
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
        times = [
            (datetime.date.fromisoformat(d) - base).days for d in dates
        ]
        perf = [
            MathTools.epley_1rm(w, r)
            for w, r in zip(weights, reps)
        ]
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
        names = self.exercise_names.fetch_all()
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
                t0 = datetime.datetime.fromisoformat(start)
                t1 = datetime.datetime.fromisoformat(end)
                durs.append((t1 - t0).total_seconds())
            else:
                durs.append(50.0)
            dates.append(date)

        uniq_dates = sorted(set(dates))
        first = datetime.date.fromisoformat(dates[0])
        ts_all = [
            (datetime.date.fromisoformat(d) - first).days for d in dates
        ]

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

        return results

    def weekly_load_variability(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, object]:
        names = self.exercise_names.fetch_all()
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
        names = self.exercise_names.fetch_all()
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

    def stress_balance(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """Return Training Stress Balance across dates."""
        names = self.exercise_names.fetch_all()
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
                t0 = datetime.datetime.fromisoformat(start)
                t1 = datetime.datetime.fromisoformat(end)
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
        return result

    def session_efficiency(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """Return efficiency score per workout."""
        names = self.exercise_names.fetch_all()
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
                t0 = datetime.datetime.fromisoformat(start)
                t1 = datetime.datetime.fromisoformat(end)
                entry["dur"] += (t1 - t0).total_seconds()
            entry["rpe"].append(int(rpe))
        result: List[Dict[str, float]] = []
        for wid, data in sorted(by_workout.items()):
            duration = float(data["dur"])
            avg_rpe = (
                sum(data["rpe"]) / len(data["rpe"])
                if data["rpe"]
                else None
            )
            eff = MathTools.session_efficiency(
                data["volume"], duration, avg_rpe
            )
            result.append(
                {
                    "workout_id": wid,
                    "date": data["date"],
                    "efficiency": round(eff, 2),
                }
            )
        return result
    def rest_times(

        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """Return average rest duration between sets per workout."""
        names = self.exercise_names.fetch_all()
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
                prev_end = datetime.datetime.fromisoformat(times_sorted[i-1][1])
                curr_start = datetime.datetime.fromisoformat(times_sorted[i][0])
                diff = (curr_start - prev_end).total_seconds()
                if diff > 0:
                    rests.append(diff)
            avg = sum(rests) / len(rests) if rests else 0.0
            result.append({"workout_id": wid, "avg_rest": round(avg, 2)})
        return result


    def stress_overview(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, float]:
        """Return overall stress and fatigue for the period."""
        names = self.exercise_names.fetch_all()
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
                t0 = datetime.datetime.fromisoformat(start)
                t1 = datetime.datetime.fromisoformat(end)
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
        names = self.exercise_names.fetch_all()
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
        ts_last = (
            datetime.date.fromisoformat(ordered_dates[-1]) - base
        ).days

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
        base = (
            MathTools.clamp(sum(features) / 3.0, 0.0, 10.0) / 10.0
        )
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
        names = self.exercise_names.fetch_all()
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
                t0 = datetime.datetime.fromisoformat(start)
                t1 = datetime.datetime.fromisoformat(end)
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
        ):
            score = self.adaptation_model.predict(features, base)
        if (
            self.adaptation_model is not None
            and self.settings is not None
            and self.settings.get_bool("ml_all_enabled", True)
            and self.settings.get_bool("ml_training_enabled", True)
        ):
            self.adaptation_model.train(features, base)
        return {"adaptation": round(score * 10.0, 2)}
