import math
import datetime
from typing import Iterable, List, Tuple
import numpy as np

class MathTools:
    """Provides essential mathematical utilities for workout calculations."""

    EPL_COEFF: float = 0.0333
    ALPHA_MIN: float = 0.75
    ALPHA_MAX: float = 1.0
    FFM_FRACTION: float = 0.407
    EA_BASELINE: float = 1.097
    L: int = 3
    W1: float = 0.4
    W2: float = 0.3
    W3: float = 0.3

    @staticmethod
    def clamp(value: float, min_value: float, max_value: float) -> float:
        """Clamp ``value`` to the inclusive range [min_value, max_value]."""
        if min_value > max_value:
            raise ValueError("min_value must not exceed max_value")
        return max(min_value, min(value, max_value))

    @classmethod
    def epley_1rm(cls, weight: float, reps: int, factor: float = 1.0) -> float:
        """Return the estimated one-rep max using the Epley formula."""
        if reps < 0:
            raise ValueError("reps must be non-negative")
        rep_term = min(reps, 8)
        return weight * (1 + cls.EPL_COEFF * rep_term) * factor

    @staticmethod
    def volume(sets: list[tuple[int, float]]) -> float:
        """Compute training volume as the sum of reps times weight."""
        vol = 0.0
        for reps, weight in sets:
            vol += reps * weight
        return vol

    @staticmethod
    def experience_score(months_active: int, workouts_per_month: int) -> int:
        """Return a simple score reflecting training experience."""
        if months_active < 0 or workouts_per_month < 0:
            raise ValueError("inputs must be non-negative")
        return months_active * workouts_per_month

    @staticmethod
    def basic_threshold(recent_avg: float, prev_avg: float) -> float:
        """Compute the relative change between recent and previous averages."""
        if prev_avg == 0:
            raise ValueError("prev_avg must not be zero")
        return (recent_avg - prev_avg) / prev_avg

    @staticmethod
    def required_progression(
        target_1rm: float, current_1rm: float, days_remaining: int
    ) -> float:
        """Return the daily 1RM progression needed to meet a target."""
        if days_remaining <= 0:
            raise ValueError("days_remaining must be positive")
        return (target_1rm - current_1rm) / days_remaining

    @staticmethod
    def warmup_weights(target_weight: float, sets: int) -> list[float]:
        """Return a list of warm-up weights leading up to ``target_weight``."""
        if target_weight <= 0 or sets <= 0:
            raise ValueError("invalid input values")
        inc = np.linspace(0.3, 0.9, sets)
        return [round(target_weight * float(i), 2) for i in inc]

    @staticmethod
    def warmup_plan(target_weight: float, target_reps: int, sets: int = 3) -> list[tuple[int, float]]:
        """Generate a warmup plan as list of (reps, weight)."""
        if target_weight <= 0 or target_reps <= 0 or sets <= 0:
            raise ValueError("invalid input values")
        weights = MathTools.warmup_weights(target_weight, sets)
        rep_range = np.linspace(target_reps + 2, max(1, target_reps // 2), sets)
        return [(int(round(r)), w) for r, w in zip(rep_range, weights)]

    @staticmethod
    def estimate_velocity_from_set(
        reps: int,
        start_time: datetime.datetime | str,
        finish_time: datetime.datetime | str,
        rom: float = 0.5,
    ) -> float:
        """Estimate mean set velocity from timing and assumed ROM."""
        if start_time is None or finish_time is None or reps <= 0:
            return 0.0
        if isinstance(start_time, str):
            start_time = datetime.datetime.fromisoformat(start_time)
        if isinstance(finish_time, str):
            finish_time = datetime.datetime.fromisoformat(finish_time)
        total_seconds = (finish_time - start_time).total_seconds()
        if total_seconds <= 0 or reps <= 0:
            return 0.0
        return (reps * rom) / total_seconds

    @staticmethod
    def estimate_power_from_set(
        reps: int,
        weight: float,
        start_time: datetime.datetime | str,
        finish_time: datetime.datetime | str,
        rom: float = 0.5,
    ) -> float:
        """Estimate average mechanical power output for a set."""
        velocity = MathTools.estimate_velocity_from_set(
            reps, start_time, finish_time, rom
        )
        if velocity == 0.0:
            return 0.0
        return float(weight) * 9.81 * velocity

    @staticmethod
    def session_efficiency(
        volume: float, duration_seconds: float, avg_rpe: float | None = None
    ) -> float:
        """Return an efficiency score for a workout session."""
        if duration_seconds <= 0:
            return 0.0
        base = volume / (duration_seconds / 60)
        rpe_adj = math.log1p(avg_rpe) if avg_rpe is not None else 1.0
        return base * rpe_adj
    @staticmethod
    def session_density(volume: float, duration_seconds: float) -> float:
        """Return training volume per minute."""
        if duration_seconds <= 0:
            return 0.0
        return volume / (duration_seconds / 60)

    @staticmethod
    def set_pace(sets: int, duration_seconds: float) -> float:
        """Return sets completed per minute."""
        if duration_seconds <= 0:
            return 0.0
        return sets / (duration_seconds / 60)

    @staticmethod
    def diversity_index(counts: Iterable[int]) -> float:
        """Return Shannon diversity index for ``counts``."""
        total = sum(counts)
        if total <= 0:
            return 0.0
        ent = 0.0
        for c in counts:
            if c > 0:
                p = c / total
                ent -= p * math.log(p, 2)
        return ent

    @staticmethod
    def coefficient_of_variation(values: Iterable[float]) -> float:
        """Return the coefficient of variation for ``values``."""
        data = list(values)
        if len(data) < 2:
            return 0.0
        arr = np.array(data, dtype=float)
        mean = float(np.mean(arr))
        if mean == 0:
            return 0.0
        std = float(np.std(arr))
        return std / mean


    @staticmethod
    def overtraining_index(stress: float, fatigue: float, variability: float) -> float:
        """Return a simple overtraining risk index."""
        base = (stress + fatigue) / 2.0
        return MathTools.clamp(base * (1 + variability), 0.0, 10.0)

    @staticmethod
    def readiness_score(stress: float, fatigue: float) -> float:
        """Return a training readiness score from stress and fatigue."""
        score = 10.0 - math.sqrt(stress**2 + fatigue**2)
        return MathTools.clamp(score, 0.0, 10.0)

    @staticmethod
    def weighted_fusion(
        model_pred: float,
        model_conf: float,
        algo_pred: float,
        algo_conf: float = 1.0,
        algo_reliability: float = 1.0,
    ) -> float:
        """Fuse model and algorithm predictions using quadratic confidence."""
        adj_algo_conf = algo_conf * max(algo_reliability, 0.0)
        model_w = model_conf**2
        algo_w = adj_algo_conf**2
        total = model_w + algo_w
        if total == 0:
            raise ValueError("total confidence cannot be zero")
        return (model_w * model_pred + algo_w * algo_pred) / total
