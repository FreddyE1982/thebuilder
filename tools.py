import math
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


class ExercisePrescription(MathTools):
    """Advanced utilities for generating detailed workout prescriptions."""

    ALPHA_MIN: float = -0.20
    ALPHA_MAX: float = 0.07
    FFM_FRACTION: float = 0.85
    EA_BASELINE: float = 40.0
    EPSILON: float = 0.0001

    @classmethod
    def _current_1rm(cls, weights: list[float], reps: list[int]) -> float:
        w = np.array(weights)
        r = np.array(reps)
        return float(np.max(w * (1 + cls.EPL_COEFF * np.minimum(r, 8))))

    @staticmethod
    def _total_volume(weights: list[float], reps: list[int]) -> float:
        w = np.array(weights)
        r = np.array(reps)
        return float(np.sum(w * r))

    @staticmethod
    def _means(values: list[float]) -> float:
        return float(np.mean(np.array(values)))

    @staticmethod
    def _slope(t: list[float], w: list[float]) -> float:
        t_arr = np.array(t)
        w_arr = np.array(w)
        t_mean = np.mean(t_arr)
        y_mean = np.mean(w_arr)
        numerator = np.sum((t_arr - t_mean) * (w_arr - y_mean))
        denominator = np.sum((t_arr - t_mean) ** 2)
        return float(numerator / denominator) if denominator != 0 else 0.0

    @classmethod
    def _recent_load(cls, weights: list[float], reps: list[int]) -> float:
        w = np.array(weights)
        r = np.array(reps)
        S = len(weights)
        start = max(0, S - cls.L)
        return float(np.mean((w * r)[start:S])) if S > 0 else 0.0

    @classmethod
    def _prev_load(cls, weights: list[float], reps: list[int]) -> float:
        w = np.array(weights)
        r = np.array(reps)
        S = len(weights)
        start = max(0, S - 2 * cls.L)
        end = max(0, S - cls.L)
        if end > start:
            return float(np.mean((w * r)[start:end]))
        recent = cls._recent_load(weights, reps)
        return recent

    @staticmethod
    def _threshold(recent: float, previous: float) -> float:
        return (recent - previous) / previous if previous != 0 else 0.0

    @staticmethod
    def _cv(weights: list[float], reps: list[int]) -> float:
        w = np.array(weights)
        r = np.array(reps)
        vols = w * r
        mean = np.mean(vols)
        return float((np.std(vols) / mean) * 100) if mean != 0 else 0.0

    @classmethod
    def _plateau(cls, slope: float, cv: float, thresh: float) -> float:
        slope_zero = 1 if abs(slope) < cls.EPSILON else 0
        cv_low = 1 if cv < 1.5 else 0
        thresh_low = 1 if thresh <= 0.02 else 0
        return cls.W1 * slope_zero + cls.W2 * cv_low + cls.W3 * thresh_low

    @staticmethod
    def _fatigue(weights: list[float], reps: list[int], timestamps: list[float], decay: float) -> float:
        w = np.array(weights)
        r = np.array(reps)
        t = np.array(timestamps)
        t_current = t[-1] if len(t) > 0 else 0.0
        vols = w * r
        return float(np.sum(vols * (decay ** (t_current - t))))

    @staticmethod
    def _ac_ratio(weights: list[float], reps: list[int]) -> float:
        w = np.array(weights)
        r = np.array(reps)
        vol = w * r
        alpha = 0.3
        recent = np.mean(vol[-7:]) if len(vol) >= 7 else np.mean(vol)
        chronic = np.mean(vol) if len(vol) > 0 else 1.0
        return float(recent / chronic) if chronic != 0 else 1.0

    @classmethod
    def _energy_availability(cls, body_weight: float, avg_calories: float | None) -> float:
        ffm = body_weight * cls.FFM_FRACTION
        if avg_calories is not None:
            ea = (avg_calories / ffm) / cls.EA_BASELINE
            return cls.clamp(ea, 0.5, 1.1)
        return 1.0

    @classmethod
    def _mrv(cls, mev: float, fatigue: float, stress: float, ea: float, theta: float) -> float:
        return mev * (1 + math.exp(theta * fatigue / 1000) - stress) * ea

    @staticmethod
    def _adj_mrv(mrv: float, perf: list[float], rec: list[float]) -> float:
        perf_f = np.mean(np.array(perf)) if len(perf) > 0 else 1.0
        rec_q = np.mean(np.array(rec)) if len(rec) > 0 else 1.0
        return mrv * perf_f * rec_q

    @staticmethod
    def _sleep_factor(avg_sleep: float | None) -> float:
        if avg_sleep is not None:
            return ExercisePrescription.clamp(1 + 0.06 * (avg_sleep - 8.0), 0.5, 1.1)
        return 1.0

    @staticmethod
    def _perceived_sleep_quality_factor(quality: float | None) -> float:
        if quality is not None:
            q = ExercisePrescription.clamp(quality, 0.0, 5.0)
            return ExercisePrescription.clamp(0.5 + 0.12 * q, 0.5, 1.1)
        return 1.0

    @classmethod
    def _sleep_recovery_index(cls, sleep_hours: float | None, quality: float | None) -> float:
        sf = cls._sleep_factor(sleep_hours)
        psqf = cls._perceived_sleep_quality_factor(quality)
        return math.sqrt(sf * psqf)

    @staticmethod
    def _experience(months_active: float, workouts_per_month: float) -> float:
        return months_active * workouts_per_month

    @staticmethod
    def _tolerance(perf: list[float], rec: list[float], target_1rm: float | None, current_1rm: float, days_remaining: int | None) -> float:
        perf_arr = np.array(perf)
        rec_arr = np.array(rec)
        if target_1rm is not None and days_remaining is not None and days_remaining > 0:
            required_rate = (target_1rm - current_1rm) / days_remaining
            if required_rate != 0:
                return float(np.sum(perf_arr * rec_arr) / abs(required_rate))
            return 1.0
        if len(perf_arr) > 0:
            return float(np.sum(perf_arr * rec_arr) / len(perf_arr))
        return 1.0

    @staticmethod
    def _volume_prescription(mev: float, mrv: float, phase_factor: float, tolerance: float) -> float:
        return mev + (mrv - mev) * phase_factor * tolerance

    @staticmethod
    def _urgency(target_1rm: float | None, current_1rm: float) -> float:
        if target_1rm is not None and target_1rm > 0:
            progress = current_1rm / target_1rm
            return 1 / (1 + math.exp(-10 * (progress - 0.5)))
        return 0.0

    @staticmethod
    def _deltas(current_1rm: float, y_mean: float, recent: float, prev: float) -> tuple[float, float]:
        delta_1rm = (current_1rm - y_mean) / y_mean if y_mean != 0 else 0.0
        delta_vol = (recent - prev) / prev if prev != 0 else 0.0
        return delta_1rm, delta_vol

    @classmethod
    def _alpha(cls, delta_1rm: float, delta_vol: float, rec: float) -> float:
        base = 0.6 * delta_1rm + 0.4 * delta_vol
        return cls.clamp(base * rec, cls.ALPHA_MIN, cls.ALPHA_MAX)

    @staticmethod
    def _required_rate(target_1rm: float | None, current_1rm: float, days_remaining: int | None) -> float:
        if target_1rm is not None and days_remaining is not None and days_remaining > 0:
            return (target_1rm - current_1rm) / days_remaining
        return 0.0

    @staticmethod
    def _achievement_probability(required_rate: float) -> float:
        if required_rate != 0:
            return min(1.0, abs(required_rate) / abs(required_rate))
        return 1.0

    @staticmethod
    def _weekly_rate(slope: float, y_mean: float) -> float:
        return (slope * 7 * 24 * 3600) / y_mean if y_mean != 0 else 0.0

    @staticmethod
    def _weekly_monotony(weights: list[float], reps: list[int]) -> float:
        w = np.array(weights)
        r = np.array(reps)
        loads = w * r
        std = np.std(loads)
        return float(np.mean(loads) / std) if std != 0 else 1.0

    @staticmethod
    def _deload_trigger(perf_factor: float, rpe_scores: list[float], rec: float) -> float:
        perf_decline = max(0.0, 1.0 - perf_factor)
        rpe_elev = max(0.0, np.mean(np.array(rpe_scores)) - 7) if len(rpe_scores) > 0 else 0.0
        return float(perf_decline * rpe_elev * (1 / rec if rec != 0 else 1.0))

    @staticmethod
    def _rpe_scale(rpe_scores: list[float]) -> float:
        arr = np.array(rpe_scores)
        mean = np.mean(arr)
        return float(np.std(arr) / mean) if len(arr) > 0 and mean != 0 else 1.0

    @staticmethod
    def _confidence_interval(slope: float, weights: list[float], times: list[float]) -> tuple[float, float]:
        w = np.array(weights)
        t = np.array(times)
        mse = np.var(w) if len(w) > 1 else 0.0
        denom = np.sum((t - np.mean(t)) ** 2)
        se = math.sqrt(mse / denom) if denom != 0 else 0.0
        return float(slope - 1.96 * se), float(slope + 1.96 * se)

    @staticmethod
    def _daily_volumes(weights: list[float], reps: list[int], times: list[float]) -> dict[int, float]:
        volumes: dict[int, float] = {}
        for w, r, t in zip(weights, reps, times):
            day = int(t)
            volumes[day] = volumes.get(day, 0.0) + w * r
        return volumes

    @classmethod
    def _performance_scores_from_logs(
        cls,
        weights: list[float],
        reps: list[int],
        times: list[float],
        mev: float,
    ) -> list[float]:
        vols = cls._daily_volumes(weights, reps, times)
        if not vols:
            return [0.5]
        avg_actual = np.mean(list(vols.values()))
        presc = mev if mev > 0 else avg_actual
        result = []
        for day in sorted(vols.keys()):
            v_i = vols.get(day, avg_actual)
            perf_i = cls.clamp(v_i / presc, 0.5, 1.5)
            result.append(perf_i)
        return result


    @classmethod
    def _recovery_scores_from_logs(
        cls,
        body_weight: float,
        calories: list[float] | None,
        sleep_hours: list[float] | None,
        sleep_quality: list[float] | None,
    ) -> list[float]:
        days = max(len(calories or []), len(sleep_hours or []), len(sleep_quality or []))
        if days == 0:
            return [1.0]
        rec_scores: list[float] = []
        for i in range(days):
            cal = calories[i] if calories and i < len(calories) else None
            slp = sleep_hours[i] if sleep_hours and i < len(sleep_hours) else None
            qual = (
                sleep_quality[i] if sleep_quality and i < len(sleep_quality) else None
            )
            ea = (
                cls.clamp(cal / ((body_weight * 0.85) * 40.0), 0.5, 1.1)
                if cal is not None
                else 1.0
            )
            sri = cls._sleep_recovery_index(slp, qual)
            rec_scores.append((ea + sri) / 2)
        return rec_scores

    @classmethod
    def exercise_prescription(
        cls,
        weights: list[float],
        reps: list[int],
        timestamps: list[float],
        rpe_scores: list[float],
        body_weight: float,
        months_active: float,
        workouts_per_month: float,
        MEV: float = 10,
        *,
        calories: list[float] | None = None,
        sleep_hours: list[float] | None = None,
        sleep_quality: list[float] | None = None,
        target_1rm: float | None = None,
        days_remaining: int | None = None,
        decay: float = 0.9,
        theta: float = 0.1,
        stress: float = 0.1,
        phase_factor: float = 0.7,
    ) -> dict:
        """Return a detailed workout prescription."""

        current_1rm = cls._current_1rm(weights, reps)
        total_volume = cls._total_volume(weights, reps)
        t_mean = cls._means(timestamps)
        y_mean = cls._means(weights)
        slope = cls._slope(timestamps, weights)
        recent_load = cls._recent_load(weights, reps)
        prev_load = cls._prev_load(weights, reps)
        thresh = cls._threshold(recent_load, prev_load)
        cv = cls._cv(weights, reps)
        plateau = cls._plateau(slope, cv, thresh)
        fatigue = cls._fatigue(weights, reps, timestamps, decay)
        ac_ratio = cls._ac_ratio(weights, reps)
        perf_scores = cls._performance_scores_from_logs(weights, reps, timestamps, MEV)
        rec_scores = cls._recovery_scores_from_logs(
            body_weight, calories, sleep_hours, sleep_quality
        )
        ea = cls._energy_availability(body_weight, np.mean(calories) if calories else None)
        mrv = cls._mrv(MEV, fatigue, stress, ea, theta)
        sri = cls._sleep_recovery_index(
            np.mean(sleep_hours) if sleep_hours else None,
            np.mean(sleep_quality) if sleep_quality else None,
        )
        adj_mrv = cls._adj_mrv(mrv, perf_scores, rec_scores)
        experience = cls._experience(months_active, workouts_per_month)
        tolerance = cls._tolerance(
            perf_scores,
            rec_scores,
            target_1rm,
            current_1rm,
            days_remaining,
        )
        vol_presc = cls._volume_prescription(MEV, mrv, phase_factor, tolerance)
        urgency = cls._urgency(target_1rm, current_1rm)
        delta_1rm, delta_vol = cls._deltas(current_1rm, y_mean, recent_load, prev_load)
        rec_factor = np.mean(np.array(rec_scores)) if len(rec_scores) > 0 else 1.0
        alpha = cls._alpha(delta_1rm, delta_vol, rec_factor)
        required_rate = cls._required_rate(target_1rm, current_1rm, days_remaining)
        achievement_prob = cls._achievement_probability(required_rate)
        weekly_rate = cls._weekly_rate(slope, y_mean)
        weekly_monotony = cls._weekly_monotony(weights, reps)
        perf_factor = np.mean(np.array(perf_scores)) if len(perf_scores) > 0 else 1.0
        deload_trigger = cls._deload_trigger(perf_factor, rpe_scores, rec_factor)
        rpe_scale = cls._rpe_scale(rpe_scores)
        confidence_int = cls._confidence_interval(slope, weights, timestamps)

        mean_vol = np.mean(np.array(weights) * np.array(reps)) if len(weights) > 0 else 1.0
        raw_sets = (
            adj_mrv
            / mean_vol
            * (1 - plateau)
            * (1 + alpha)
            * (1 + urgency)
            * cls.clamp(1 - fatigue / mrv, 0.6, 1.0)
            * cls.clamp(1 - weekly_monotony / 2, 0.5, 1.0)
            * cls.clamp(achievement_prob, 0.6, 1.0)
        )
        N = int(cls.clamp(round(raw_sets), 1, 10))

        deload_needed = deload_trigger >= 1.0 or (confidence_int[0] <= 0 <= confidence_int[1])
        if deload_needed:
            N = int(cls.clamp(math.ceil(N / 2), 1, 4))

        base_reps = (
            round(np.mean(np.array(reps)) * (1 + alpha * (1 - plateau))) if len(reps) > 0 else 8
        )
        intensity_target = 0.75 if base_reps >= 6 else 0.85

        sets_prescription: list[dict] = []
        for k in range(1, N + 1):
            prog_drop = (k - 1) / (N - 1 + 1e-9)
            reps_k = cls.clamp(
                round(
                    base_reps
                    * (1 - prog_drop * thresh)
                    * (1 - weekly_rate / (abs(weekly_rate) + 1))
                ),
                1,
                20,
            )
            if deload_needed:
                reps_k = math.ceil(0.7 * reps_k)
            load_decay = 1 - prog_drop * 0.05
            weight_k = cls.clamp(
                current_1rm
                * intensity_target
                * load_decay
                * (1 - 0.1 * plateau)
                * ea
                * sri,
                0.5 * y_mean,
                0.95 * current_1rm,
            )
            if deload_needed:
                weight_k *= 0.8
            target_rpe = cls.clamp(7 + 0.3 * plateau, 6, 9)
            rest_k = 90 + 30 * rpe_scale + 15 * (reps_k < 5) + 10 * k
            sets_prescription.append(
                {
                    "set": k,
                    "reps": int(reps_k),
                    "weight": round(weight_k, 1),
                    "target_rpe": round(target_rpe, 1),
                    "rest_seconds": int(rest_k),
                }
            )

        result = {
            "prescription": sets_prescription,
            "total_sets": N,
            "deload_recommended": deload_needed,
            "analysis": {
                "current_1RM": round(current_1rm, 1),
                "plateau_score": round(plateau, 2),
                "fatigue_level": round(fatigue / 1000, 2),
                "progression_modifier": round(alpha, 3),
                "urgency_factor": round(urgency, 2),
                "achievement_probability": round(achievement_prob, 2),
                "ac_ratio": round(ac_ratio, 2),
                "weekly_monotony": round(weekly_monotony, 2),
                "deload_trigger": round(deload_trigger, 2),
            },
            "recommendations": {
                "focus": "strength" if intensity_target > 0.8 else "hypertrophy",
                "volume_status": "optimal"
                if 0.8 <= ac_ratio <= 1.3
                else "adjust",
                "recovery_needed": deload_needed,
            },
        }
        return result



class ExerciseProgressEstimator(ExercisePrescription):
    """Utility for forecasting 1RM progression using prescription logic."""

    @classmethod
    def predict_progress(
        cls,
        weights: list[float],
        reps: list[int],
        timestamps: list[float],
        rpe_scores: list[int],
        weeks: int,
        workouts_per_week: int,
        *,
        body_weight: float,
        months_active: float,
        workouts_per_month: float,
    ) -> list[dict]:
        """Predict future 1RM values for several weeks."""

        w_hist = list(weights)
        r_hist = list(reps)
        t_hist = list(timestamps)
        rpe_hist = list(rpe_scores)
        current_time = t_hist[-1] if t_hist else 0.0
        forecast: list[dict] = []

        for week in range(1, weeks + 1):
            for _ in range(workouts_per_week):
                presc = cls.exercise_prescription(
                    w_hist,
                    r_hist,
                    t_hist,
                    rpe_hist,
                    body_weight=body_weight,
                    months_active=months_active,
                    workouts_per_month=workouts_per_month,
                )
                data = presc["prescription"][0]
                current_time += 1
                t_hist.append(current_time)
                w_hist.append(float(data["weight"]))
                r_hist.append(int(data["reps"]))
                rpe_hist.append(int(round(data["target_rpe"])))

            est = cls._current_1rm(w_hist, r_hist)
            forecast.append({"week": week, "est_1rm": round(est, 2)})

        return forecast
