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
