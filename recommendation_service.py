from __future__ import annotations
import datetime
from db import (
    WorkoutRepository,
    ExerciseRepository,
    SetRepository,
    ExerciseNameRepository,
    SettingsRepository,
)
from tools import ExercisePrescription
from gamification_service import GamificationService
from ml_service import PerformanceModelService, RLGoalModelService, weighted_fusion


class RecommendationService:
    """Generate exercise set recommendations based on logged history."""

    def __init__(
        self,
        workout_repo: WorkoutRepository,
        exercise_repo: ExerciseRepository,
        set_repo: SetRepository,
        exercise_name_repo: ExerciseNameRepository,
        settings_repo: SettingsRepository,
        gamification: GamificationService | None = None,
        ml_service: PerformanceModelService | None = None,
        rl_goal: "RLGoalModelService" | None = None,
    ) -> None:
        self.workouts = workout_repo
        self.exercises = exercise_repo
        self.sets = set_repo
        self.exercise_names = exercise_name_repo
        self.settings = settings_repo
        self.gamification = gamification
        self.ml = ml_service
        self.rl_goal = rl_goal
        self._pending: dict[int, list[float]] = {}

    def has_history(self, exercise_name: str) -> bool:
        names = self.exercise_names.aliases(exercise_name)
        history = self.sets.fetch_history_by_names(names)
        return len(history) > 0

    def recommend_next_set(self, exercise_id: int) -> dict:
        workout_id, name, _ = self.exercises.fetch_detail(exercise_id)
        alias_names = self.exercise_names.aliases(name)
        history = self.sets.fetch_history_by_names(
            alias_names, with_duration=True, with_workout_id=True
        )
        if not history:
            raise ValueError("no history for exercise")
        reps_list = [int(r[0]) for r in history]
        weight_list = [float(r[1]) for r in history]
        rpe_list = [int(r[2]) for r in history]
        durations = []
        rest_times: list[float] = []
        prev_end: datetime.datetime | None = None
        session_map: dict[int, dict] = {}
        for r in history:
            start = r[4]
            end = r[5]
            wid = r[6]
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
            sess = session_map.setdefault(wid, {"volume": 0.0, "rpe": []})
            sess["volume"] += int(r[0]) * float(r[1])
            sess["rpe"].append(int(r[2]))
        dates = [datetime.date.fromisoformat(r[3]) for r in history]
        timestamps = list(range(len(dates)))
        months_active = self.settings.get_float("months_active", 1.0)
        workouts_per_month = float(len(set(timestamps)))

        sessions: list[dict] = []
        for wid in session_map:
            wid_d, date, start, end, t_type = self.workouts.fetch_detail(wid)
            sessions.append(
                {
                    "id": wid_d,
                    "start": datetime.datetime.fromisoformat(start) if start else None,
                    "end": datetime.datetime.fromisoformat(end) if end else None,
                    "type": t_type,
                    "volume": session_map[wid]["volume"],
                    "avg_rpe": (
                        float(
                            sum(session_map[wid]["rpe"]) / len(session_map[wid]["rpe"])
                        )
                        if session_map[wid]["rpe"]
                        else 6.0
                    ),
                }
            )
        sessions.sort(key=lambda x: x["start"] or datetime.datetime.min)
        recovery_times: list[float] = []
        optimal_times: list[float] = []
        for prev, curr in zip(sessions, sessions[1:]):
            if prev["end"] and curr["start"]:
                rt = (curr["start"] - prev["end"]).total_seconds() / 3600
                base = 48 + (prev["avg_rpe"] - 6) * 12
                if prev["type"] == "highintensity":
                    base = max(base, 72)
                opt = ExercisePrescription.clamp(base, 24, 96)
                recovery_times.append(rt)
                optimal_times.append(opt)
        recovery_qualities = [
            ExercisePrescription.clamp(rt / ot, 0.3, 2.0)
            for rt, ot in zip(recovery_times, optimal_times)
        ]
        recovery_quality_mean = (
            float(
                sum(recovery_qualities[-ExercisePrescription.L :])
                / len(recovery_qualities[-ExercisePrescription.L :])
            )
            if recovery_qualities
            else 1.0
        )
        avg_recovery_time = (
            float(sum(recovery_times[-4:]) / len(recovery_times[-4:]))
            if len(recovery_times) >= 4
            else 72.0
        )
        frequency_factor = ExercisePrescription.clamp(72 / avg_recovery_time, 0.5, 2.0)
        session_volumes = [s["volume"] for s in sessions[:-1]]
        prescription = ExercisePrescription.exercise_prescription(
            weight_list,
            reps_list,
            timestamps,
            rpe_list,
            durations=durations,
            rest_times=rest_times,
            recovery_times=recovery_times,
            optimal_recovery_times=optimal_times,
            session_volumes=session_volumes,
            recovery_quality_mean=recovery_quality_mean,
            frequency_factor=frequency_factor,
            body_weight=self.settings.get_float("body_weight", 80.0),
            months_active=months_active,
            workouts_per_month=workouts_per_month,
            exercise_name=name,
        )
        current_sets = self.sets.fetch_for_exercise(exercise_id)
        index = len(current_sets)
        if index >= len(prescription["prescription"]):
            raise ValueError("no more sets recommended")
        data = prescription["prescription"][index]
        if (
            self.ml
            and self.settings.get_bool("ml_all_enabled", True)
            and self.settings.get_bool("ml_prediction_enabled", True)
            and self.settings.get_bool("ml_rpe_prediction_enabled", True)
        ):
            ml_rpe, conf = self.ml.predict(
                name,
                int(data["reps"]),
                float(data["weight"]),
                rpe_list[-1],
            )
            data["target_rpe"] = float(
                weighted_fusion(ml_rpe, conf, float(data["target_rpe"]))
            )
        action = 1
        state: list[float] | None = None
        if (
            self.rl_goal
            and self.settings.get_bool("ml_all_enabled", True)
            and self.settings.get_bool("ml_prediction_enabled", True)
            and self.settings.get_bool("ml_goal_prediction_enabled", True)
        ):
            state = [
                weight_list[-1] / 1000.0,
                reps_list[-1] / 10.0,
                rpe_list[-1] / 10.0,
            ]
            action = self.rl_goal.predict(state)
            data["weight"] = float(data["weight"] + self.rl_goal.ACTIONS[action])
        set_id = self.sets.add(
            exercise_id,
            int(data["reps"]),
            float(data["weight"]),
            int(round(data["target_rpe"])),
        )
        if state is not None:
            self.rl_goal.register(set_id, state, action)
        if self.gamification:
            self.gamification.record_set(
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

    def record_result(self, set_id: int, reps: int, weight: float, rpe: int) -> None:
        if self.rl_goal and set_id in self.rl_goal.pending:
            new_state = [weight / 1000.0, reps / 10.0, rpe / 10.0]
            reward = 1.0 - abs(rpe - 8.0) / 10.0
            self.rl_goal.complete(set_id, new_state, reward)
