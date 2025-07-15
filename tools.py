import math
from typing import Iterable

import numpy as np
import pandas as pd
from statsmodels.tsa.ar_model import AutoReg
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.vector_ar.var_model import VAR
import pywt
import warnings


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
    def _ewma(values: Iterable[float], span: int) -> list[float]:
        series = pd.Series(list(values))
        return list(series.ewm(span=span, adjust=False).mean())

    @staticmethod
    def _ar_decay(values: Iterable[float]) -> float:
        data = list(values)
        if len(data) < 5 or np.std(data) == 0:
            return 1.0
        try:
            model = AutoReg(data, lags=1, old_names=False).fit()
        except Exception:
            return 1.0
        if len(model.params) < 2:
            return 1.0
        phi = float(model.params[1])
        return MathTools.clamp(phi, 0.5, 1.5)

    @staticmethod
    def _cross_correlation(
        x: Iterable[float], y: Iterable[float], max_lag: int = 7
    ) -> tuple[int, float]:
        x_arr = np.array(list(x))
        y_arr = np.array(list(y))
        best_lag = 0
        best_corr = 0.0
        for lag in range(-max_lag, max_lag + 1):
            if lag < 0:
                a = x_arr[:lag]
                b = y_arr[-lag:]
            elif lag > 0:
                a = x_arr[lag:]
                b = y_arr[:-lag]
            else:
                a = x_arr
                b = y_arr
            if len(a) <= 1 or len(b) <= 1 or np.std(a) == 0 or np.std(b) == 0:
                corr = 0.0
            else:
                corr = float(np.corrcoef(a, b)[0, 1])
            if np.isnan(corr):
                corr = 0.0
            if abs(corr) > abs(best_corr):
                best_corr = corr
                best_lag = lag
        return best_lag, best_corr

    @staticmethod
    def _seasonal_components(values: Iterable[float], period: int) -> tuple[list[float], list[float]]:
        series = pd.Series(list(values))
        try:
            res = seasonal_decompose(series, period=period, model="additive", two_sided=False, extrapolate_trend="freq")
            trend = [float(v) if v is not None else 0.0 for v in res.trend]
            seasonal = [float(v) for v in res.seasonal]
        except Exception:
            trend = list(series)
            seasonal = [0.0 for _ in series]
        return trend, seasonal

    @staticmethod
    def _change_point(weights: list[float], times: list[float]) -> int:
        if len(weights) < 4 or len(weights) != len(times):
            return -1
        slopes = np.diff(np.array(weights)) / np.diff(np.array(times))
        prev_pos = slopes[0] > 0
        for i, s in enumerate(slopes[1:], start=1):
            if prev_pos and s <= 0:
                return i
            prev_pos = s > 0
        return len(weights) - 1

    @staticmethod
    def _var_forecast(weights: list[float], reps: list[int], steps: int = 1) -> float:
        if len(weights) < 3 or len(weights) != len(reps):
            return weights[-1] if weights else 0.0
        data = [[w, r] for w, r in zip(weights, reps)]
        try:
            model = VAR(data)
            res = model.fit(maxlags=1, trend="n")
            pred = res.forecast(res.endog, steps=steps)
            return float(pred[-1][0])
        except Exception:
            return float(weights[-1])

    @staticmethod
    def _kalman_filter(values: list[float], process_var: float = 1e-5, measurement_var: float = 0.1) -> list[float]:
        if not values:
            return []
        x_est = values[0]
        p = 1.0
        result = [x_est]
        for z in values[1:]:
            p += process_var
            k = p / (p + measurement_var)
            x_est = x_est + k * (z - x_est)
            p = (1 - k) * p
            result.append(x_est)
        return result

    @staticmethod
    def _wavelet_energy(values: list[float]) -> tuple[float, float, float]:
        if len(values) < 2:
            return 0.0, 0.0, 0.0
        wave = pywt.Wavelet("db1")
        max_level = pywt.dwt_max_level(len(values), wave.dec_len)
        level = min(2, max_level)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            coeffs = pywt.wavedec(values, wave, level=level)
        energies = [float(np.sum(np.square(c))) for c in coeffs]
        while len(energies) < 3:
            energies.append(0.0)
        return tuple(energies[:3])

    @staticmethod
    def _anomaly_score(values: list[float]) -> float:
        arr = np.array(values)
        if len(arr) < 2:
            return 0.0
        mean = np.mean(arr)
        std = np.std(arr)
        if std == 0:
            return 0.0
        return float(abs((arr[-1] - mean) / std))

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
    def _plateau(
        cls,
        slope: float,
        cv: float,
        thresh: float,
        weights: list[float] | None = None,
        times: list[float] | None = None,
    ) -> float:
        slope_zero = 1 if abs(slope) < cls.EPSILON else 0
        cv_low = 1 if cv < 1.5 else 0
        thresh_low = 1 if thresh <= 0.02 else 0
        change = 0.0
        if weights is not None and times is not None and len(weights) >= 6:
            mid = len(weights) // 2
            s1 = cls._slope(times[:mid], weights[:mid])
            s2 = cls._slope(times[mid:], weights[mid:])
            if s1 > 0 and s2 <= 0:
                change = 1.0
            cp = cls._change_point(weights, times)
            if 0 < cp < len(weights) - 1:
                change += 0.5
            anomaly = cls._anomaly_score(weights)
            change += min(anomaly / 3, 0.5)
            trend, seasonal = cls._seasonal_components(weights, period=7)
            season_effect = abs(seasonal[-1]) / (abs(trend[-1]) + cls.EPSILON)
            change += min(season_effect, 0.5)
        return cls.W1 * slope_zero + cls.W2 * cv_low + cls.W3 * thresh_low + 0.2 * change

    @staticmethod
    def _fatigue(
        weights: list[float],
        reps: list[int],
        timestamps: list[float],
        decay: float,
        durations: list[float] | None = None,
        ideal_tut: float = 50.0,
        rest_efficiencies: list[float] | None = None,
    ) -> float:
        w = np.array(weights)
        r = np.array(reps)
        t = np.array(timestamps)
        dur = np.array(durations) if durations is not None else np.ones_like(t) * ideal_tut
        rest_eff = (
            np.array(rest_efficiencies)
            if rest_efficiencies is not None
            else np.ones_like(t)
        )
        t_current = t[-1] if len(t) > 0 else 0.0
        vols = w * r * (dur / ideal_tut) * (2.0 - rest_eff)
        decay_mod = decay * ExercisePrescription._ar_decay(vols)
        corr = 0.0
        if rest_efficiencies is not None:
            _, corr = ExercisePrescription._cross_correlation(vols, rest_eff)
        trend, seasonal = ExercisePrescription._seasonal_components(vols, period=7)
        wave_low, wave_mid, wave_high = ExercisePrescription._wavelet_energy(list(vols))
        seasonal_factor = 1 + abs(seasonal[-1]) / (abs(trend[-1]) + 1e-9)
        wave_factor = 1 + wave_high / (wave_low + wave_mid + 1e-9)
        base = np.sum(vols * (decay_mod ** (t_current - t)))
        return float(base * (1 + abs(corr)) * seasonal_factor * wave_factor)

    @staticmethod
    def _ac_ratio(weights: list[float], reps: list[int]) -> float:
        w = np.array(weights)
        r = np.array(reps)
        vol = w * r
        if len(vol) == 0:
            return 1.0
        recent = ExercisePrescription._ewma(vol, span=7)[-1]
        chronic = ExercisePrescription._ewma(vol, span=28)[-1]
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
    def _exp_smooth(values: Iterable[float], alpha: float) -> list[float]:
        it = iter(values)
        try:
            first = float(next(it))
        except StopIteration:
            return []
        result = [first]
        prev = first
        for v in it:
            prev = alpha * float(v) + (1 - alpha) * prev
            result.append(prev)
        return result

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
        corr = 0.0
        if len(perf_arr) > 1 and len(rec_arr) > 1:
            _, corr = ExercisePrescription._cross_correlation(perf_arr, rec_arr, max_lag=3)
        base: float
        if target_1rm is not None and days_remaining is not None and days_remaining > 0:
            required_rate = (target_1rm - current_1rm) / days_remaining
            if required_rate != 0:
                base = float(np.sum(perf_arr * rec_arr) / abs(required_rate))
            else:
                base = 1.0
        elif len(perf_arr) > 0:
            base = float(np.sum(perf_arr * rec_arr) / len(perf_arr))
        else:
            base = 1.0
        return base * (1 + corr / 2)

    @staticmethod
    def _volume_prescription(mev: float, mrv: float, phase_factor: float, tolerance: float) -> float:
        base = mev + (mrv - mev) * phase_factor * tolerance
        smoothed = ExercisePrescription._exp_smooth([mev, mrv, base], 0.3)
        return smoothed[-1]

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
    def _alpha(
        cls,
        delta_1rm: float,
        delta_vol: float,
        rec: float,
        weights: list[float] | None = None,
        experience: float | None = None,
    ) -> float:
        base = 0.6 * delta_1rm + 0.4 * delta_vol
        trend = 1.0
        if weights is not None and len(weights) >= 3:
            diffs = np.diff(np.array(weights))
            trend = cls._ar_decay(diffs)
            forecast = cls._var_forecast(weights, [1] * len(weights))
            smooth = cls._kalman_filter(weights)[-1]
            if smooth != 0:
                trend *= cls.clamp(forecast / smooth, 0.8, 1.2)
        exp_factor = 1.0
        if experience is not None:
            exp_factor = cls.clamp(1 + math.log1p(experience) / 200, 1.0, 1.1)
        return cls.clamp(base * rec * trend * exp_factor, cls.ALPHA_MIN, cls.ALPHA_MAX)

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
    def _deload_trigger(
        perf_factor: float,
        rpe_scores: list[float],
        rec: float,
        tut_ratio: float = 1.0,
    ) -> float:
        perf_decline = max(0.0, 1.0 - perf_factor)
        rpe_elev = max(0.0, np.mean(np.array(rpe_scores)) - 7) if len(rpe_scores) > 0 else 0.0
        base = perf_decline * rpe_elev * (1 / rec if rec != 0 else 1.0)
        return float(base / tut_ratio)

    @staticmethod
    def _duration_error(durations: list[float], ideal: float) -> float:
        if not durations:
            return 0.0
        arr = np.array(durations)
        mean_tut = np.mean(arr)
        return float((mean_tut - ideal) / ideal)

    def _rpe_scale(
        rpe_scores: list[float],
        durations: list[float] | None = None,
        ideal_tut: float = 50.0,
    ) -> float:
        arr = np.array(rpe_scores)
        mean = np.mean(arr)
        base = float(np.std(arr) / mean) if len(arr) > 0 and mean != 0 else 1.0
        if durations:
            base *= 1 + ExercisePrescription._duration_error(durations, ideal_tut)
        return base

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
        durations: list[float] | None = None,
        rest_times: list[float] | None = None,
        recovery_times: list[float] | None = None,
        optimal_recovery_times: list[float] | None = None,
        session_volumes: list[float] | None = None,
        recovery_quality_mean: float | None = None,
        frequency_factor: float | None = None,
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
        plateau = cls._plateau(slope, cv, thresh, weights, timestamps)
        rest_efficiencies = None
        if rest_times is not None:
            optimal_rests: list[float] = []
            for rep_count in reps:
                if rep_count <= 5:
                    optimal_rests.append(240)
                elif rep_count <= 12:
                    optimal_rests.append(90)
                else:
                    optimal_rests.append(45)
            rest_efficiencies = [
                cls.clamp(opt / actual if actual > 0 else 2.0, 0.5, 2.0)
                for opt, actual in zip(optimal_rests, rest_times)
            ]
        base_fatigue = cls._fatigue(
            weights,
            reps,
            timestamps,
            decay,
            durations,
            50.0,
            rest_efficiencies,
        )

        recovery_fatigue = 0.0
        if (
            recovery_times
            and optimal_recovery_times
            and session_volumes
            and len(recovery_times)
            == len(optimal_recovery_times)
            == len(session_volumes)
        ):
            for vol, rt, ot in zip(session_volumes, recovery_times, optimal_recovery_times):
                ratio = rt / ot if ot != 0 else 1.0
                recovery_fatigue += vol * (decay ** ratio)

        fatigue = base_fatigue + recovery_fatigue
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
        if rest_efficiencies is not None and len(rest_efficiencies) > 0:
            rest_volume_modifier = float(np.mean(rest_efficiencies[-cls.L:]))
            adj_mrv *= rest_volume_modifier
        if frequency_factor is not None and recovery_quality_mean is not None:
            adj_mrv *= frequency_factor * recovery_quality_mean
        experience = cls._experience(months_active, workouts_per_month)
        tolerance = cls._tolerance(
            perf_scores,
            rec_scores,
            target_1rm,
            current_1rm,
            days_remaining,
        )
        vol_presc = cls._volume_prescription(MEV, mrv, phase_factor, tolerance)
        if session_volumes:
            forecast_vol = cls._var_forecast(session_volumes, [1] * len(session_volumes))
            vol_presc = (vol_presc + forecast_vol) / 2
        urgency = cls._urgency(target_1rm, current_1rm)
        delta_1rm, delta_vol = cls._deltas(current_1rm, y_mean, recent_load, prev_load)
        rec_factor = np.mean(np.array(rec_scores)) if len(rec_scores) > 0 else 1.0
        alpha = cls._alpha(delta_1rm, delta_vol, rec_factor, weights, experience)
        required_rate = cls._required_rate(target_1rm, current_1rm, days_remaining)
        achievement_prob = cls._achievement_probability(required_rate)
        weekly_rate = cls._weekly_rate(slope, y_mean)
        weekly_monotony = cls._weekly_monotony(weights, reps)
        perf_factor = np.mean(np.array(perf_scores)) if len(perf_scores) > 0 else 1.0
        tut_ratio = (
            float(np.sum(durations)) / (50.0 * len(durations)) if durations else 1.0
        )
        deload_trigger = cls._deload_trigger(perf_factor, rpe_scores, rec_factor, tut_ratio)
        rpe_scale = cls._rpe_scale(rpe_scores, durations, 50.0)
        confidence_int = cls._confidence_interval(slope, weights, timestamps)

        mean_vol = np.mean(np.array(weights) * np.array(reps)) if len(weights) > 0 else 1.0
        vol_factor = cls.clamp(math.log1p(total_volume) / 8, 0.95, 1.05)
        time_factor = cls.clamp(
            1 + (timestamps[-1] - t_mean) / (10 * (timestamps[-1] + cls.EPSILON)),
            0.95,
            1.05,
        )
        exp_factor = cls.clamp(1 + math.log1p(experience) / 200, 1.0, 1.1)
        raw_sets = (
            adj_mrv
            / mean_vol
            * (1 - plateau)
            * (1 + alpha)
            * (1 + urgency)
            * cls.clamp(1 - fatigue / mrv, 0.6, 1.0)
            * cls.clamp(1 - weekly_monotony / 2, 0.5, 1.0)
            * cls.clamp(achievement_prob, 0.6, 1.0)
            * vol_factor
            * time_factor
            * exp_factor
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
