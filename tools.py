import math
import datetime
from typing import Iterable, List, Tuple
from db import PyramidTestRepository, PyramidEntryRepository

import numpy as np
import pandas as pd
from statsmodels.tsa.ar_model import AutoReg
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.vector_ar.var_model import VAR
from statsmodels.tsa.arima.model import ARIMA
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
    def overtraining_index(stress: float, fatigue: float, variability: float) -> float:
        """Return a simple overtraining risk index."""
        base = (stress + fatigue) / 2.0
        return MathTools.clamp(base * (1 + variability), 0.0, 10.0)


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
    def _linear_interpolate(x: List[float], y: List[float], x_new: float) -> float:
        if not x or not y:
            return 0.0
        if len(x) == 1:
            return float(y[0])
        return float(np.interp(x_new, x, y))

    @staticmethod
    def _weighted_linear_regression(
        x: List[float], y: List[float], weights: List[float]
    ) -> float:
        if len(x) < 2 or len(x) != len(y) or len(weights) != len(x):
            return 0.0
        x_arr = np.array(x)
        y_arr = np.array(y)
        w_arr = np.array(weights)
        x_mean = np.average(x_arr, weights=w_arr)
        y_mean = np.average(y_arr, weights=w_arr)
        num = np.sum(w_arr * (x_arr - x_mean) * (y_arr - y_mean))
        den = np.sum(w_arr * (x_arr - x_mean) ** 2) + ExercisePrescription.EPSILON
        return float(num / den)

    @staticmethod
    def _linear_regression_slope(x: List[float], y: List[float]) -> float:
        if len(x) < 2 or len(x) != len(y):
            return 0.0
        x_arr = np.array(x)
        y_arr = np.array(y)
        x_mean = np.mean(x_arr)
        y_mean = np.mean(y_arr)
        num = np.sum((x_arr - x_mean) * (y_arr - y_mean))
        den = np.sum((x_arr - x_mean) ** 2)
        return float(num / den) if den != 0 else 0.0

    @staticmethod
    def _calculate_r_squared(x: List[float], y: List[float]) -> float:
        if len(x) < 2 or len(x) != len(y):
            return 0.0
        slope = ExercisePrescription._linear_regression_slope(x, y)
        intercept = np.mean(y) - slope * np.mean(x)
        pred = [slope * xi + intercept for xi in x]
        ss_tot = np.sum((np.array(y) - np.mean(y)) ** 2)
        ss_res = np.sum((np.array(y) - np.array(pred)) ** 2)
        return float(1 - ss_res / (ss_tot + ExercisePrescription.EPSILON))

    @staticmethod
    def _detect_change_points(values: List[float]) -> List[int]:
        if len(values) < 3:
            return []
        diffs = np.diff(np.array(values))
        change_points: List[int] = []
        sign = diffs[0] >= 0
        for idx, d in enumerate(diffs[1:], start=1):
            cur = d >= 0
            if cur != sign:
                change_points.append(idx)
                sign = cur
        return change_points

    @staticmethod
    def _process_pyramid_tests(
        exercise_name: str | None = None,
    ) -> Tuple[List[float], List[float], List[List[float]], List[dict[str, float]]]:
        """Load pyramid tests and convert to timestamps filtered by exercise.

        Returns timestamps, max 1RM values, list of weight series for each test,
        and progression metrics for every test."""
        repo_t = PyramidTestRepository()
        repo_e = PyramidEntryRepository()
        rows = repo_t.fetch_full_with_weights(repo_e)
        history = [r for r in rows if not exercise_name or r[1] == exercise_name]
        history.sort(key=lambda r: r[2])
        if not history:
            return [], [], [], []
        dates = [datetime.date.fromisoformat(r[2]) for r in history]
        first = dates[0]
        ts = [(d - first).days for d in dates]
        rms = [float(r[6]) if r[6] is not None else max(r[-1]) for r in history]
        weights = [r[-1] for r in history]
        metrics = [ExercisePrescription._pyramid_progression_metrics(w) for w in weights]
        return ts, rms, weights, metrics

    @staticmethod
    def _pyramid_progression_metrics(weights: List[float]) -> dict[str, float]:
        if len(weights) < 2:
            return {
                "increment_coeff": 0.0,
                "fatigue_decay": 0.0,
                "strength_reserve": 0.0,
                "efficiency_score": 1.0,
            }

        increments = [weights[i + 1] - weights[i] for i in range(len(weights) - 1)]
        mean_inc = np.mean(increments)
        inc_coeff = float(
            np.std(increments) / (mean_inc + ExercisePrescription.EPSILON)
        )
        slope = ExercisePrescription._slope(list(range(len(increments))), increments)
        efficiency = float(weights[-1] / (sum(weights) / len(weights)))
        reserve = (
            (weights[-1] - weights[-2])
            / (weights[-2] + ExercisePrescription.EPSILON)
            if len(weights) >= 2
            else 0.0
        )

        return {
            "increment_coeff": inc_coeff,
            "fatigue_decay": -slope,
            "strength_reserve": reserve,
            "efficiency_score": efficiency,
        }

    @classmethod
    def _enhanced_1rm_calculation(
        cls,
        weights: List[float],
        reps: List[int],
        pyramid_timestamps: List[float],
        pyramid_1rms: List[float],
        current_timestamp: float,
    ) -> float:
        epley = (
            max([w * (1 + cls.EPL_COEFF * min(r, 8)) for w, r in zip(weights, reps)])
            if weights
            else 0.0
        )
        if not pyramid_1rms:
            return epley
        if len(pyramid_1rms) >= 2:
            interp = ExercisePrescription._linear_interpolate(
                pyramid_timestamps,
                pyramid_1rms,
                current_timestamp,
            )
            pyr_w = 0.7
            epl_w = 0.3
            days_since = current_timestamp - pyramid_timestamps[-1]
            if days_since > 14:
                pyr_w = max(0.4, pyr_w - days_since * 0.01)
                epl_w = 1.0 - pyr_w
            return pyr_w * interp + epl_w * epley
        last = pyramid_1rms[-1]
        days_since = current_timestamp - pyramid_timestamps[-1]
        influence = math.exp(-days_since / 21)
        return influence * last + (1 - influence) * epley

    @staticmethod
    def _pyramid_enhanced_progression(
        pyramid_timestamps: List[float],
        pyramid_1rms: List[float],
        target_1rm: float | None = None,
        days_remaining: int | None = None,
    ) -> float:
        if len(pyramid_1rms) < 3:
            return 0.0
        weights = [math.exp(-(pyramid_timestamps[-1] - t) / 30) for t in pyramid_timestamps]
        actual_rate = ExercisePrescription._weighted_linear_regression(
            pyramid_timestamps,
            pyramid_1rms,
            weights,
        )
        if target_1rm and days_remaining:
            current = pyramid_1rms[-1]
            required = (target_1rm - current) / days_remaining
            if required != 0:
                adj = min(actual_rate / required, 2.0)
                return adj
        return actual_rate

    @staticmethod
    def _pyramid_enhanced_fatigue(
        pyramid_timestamps: List[float],
        pyramid_1rms: List[float],
        pyramid_weights: List[List[float]],
        pyramid_metrics: List[dict[str, float]],
        base_fatigue: float,
        current_timestamp: float,
    ) -> float:
        if len(pyramid_1rms) < 2:
            return base_fatigue
        slope, intercept = np.polyfit(pyramid_timestamps, pyramid_1rms, 1)
        indicators: List[float] = []
        for t, rm in zip(pyramid_timestamps[-5:], pyramid_1rms[-5:]):
            expected = slope * t + intercept
            diff = (rm - expected) / (expected + ExercisePrescription.EPSILON)
            days_ago = current_timestamp - t
            weight = math.exp(-days_ago / 14)
            indicators.append(diff * weight)
        if indicators:
            factor = 1.0 + abs(min(sum(indicators), 0.0)) * 0.5
            base_fatigue *= factor
        if pyramid_metrics:
            weights = [math.exp(-(current_timestamp - t) / 30) for t in pyramid_timestamps]
            total = sum(weights)
            avg_decay = sum(m["fatigue_decay"] * w for m, w in zip(pyramid_metrics, weights)) / (total + ExercisePrescription.EPSILON)
            avg_reserve = sum(m["strength_reserve"] * w for m, w in zip(pyramid_metrics, weights)) / (total + ExercisePrescription.EPSILON)
            if avg_decay > 0.2:
                base_fatigue *= 1.1
            if avg_reserve < 0.05:
                base_fatigue *= 1.05
            elif avg_reserve > 0.15:
                base_fatigue *= 0.95
        return base_fatigue

    @classmethod
    def _pyramid_enhanced_alpha(
        cls,
        base_alpha: float,
        pyramid_timestamps: List[float],
        pyramid_1rms: List[float],
        pyramid_weights: List[List[float]],
        pyramid_metrics: List[dict[str, float]],
        current_timestamp: float,
    ) -> float:
        if len(pyramid_1rms) < 2:
            return base_alpha
        recent = [
            (t, rm)
            for t, rm in zip(pyramid_timestamps, pyramid_1rms)
            if current_timestamp - t <= 30
        ]
        if len(recent) >= 2:
            actual_progress = (recent[-1][1] - recent[0][1]) / (
                recent[0][1] + cls.EPSILON
            )
            if actual_progress > 0.05:
                bonus = min(actual_progress * 0.3, 0.03)
                return cls.clamp(base_alpha + bonus, -0.20, 0.07)
            if actual_progress < -0.02:
                penalty = max(actual_progress * 0.5, -0.05)
                base_alpha = cls.clamp(base_alpha + penalty, -0.20, 0.07)
        if pyramid_metrics:
            weights = [math.exp(-(current_timestamp - t) / 30) for t in pyramid_timestamps]
            total = sum(weights)
            avg_inc = sum(m["increment_coeff"] * w for m, w in zip(pyramid_metrics, weights)) / (total + cls.EPSILON)
            avg_eff = sum(m["efficiency_score"] * w for m, w in zip(pyramid_metrics, weights)) / (total + cls.EPSILON)
            avg_reserve = sum(m["strength_reserve"] * w for m, w in zip(pyramid_metrics, weights)) / (total + cls.EPSILON)
            if avg_inc < 0.2:
                base_alpha *= 1.02
            if avg_eff > 1.1:
                base_alpha *= 1.03
            if avg_reserve > 0.15:
                base_alpha *= 1.05
            elif avg_reserve < 0.05:
                base_alpha *= 0.97
        return cls.clamp(base_alpha, -0.20, 0.07)

    @staticmethod
    def _analyze_1rm_trends(
        pyramid_timestamps: List[float], pyramid_1rms: List[float]
    ) -> dict:
        if len(pyramid_1rms) < 4:
            return {"trend": "insufficient_data"}
        if len(pyramid_1rms) >= 12:
            trend, seasonal = ExercisePrescription._seasonal_components(
                pyramid_1rms,
                period=4,
            )
            strength = np.var(seasonal) / (np.var(pyramid_1rms) + ExercisePrescription.EPSILON)
            return {
                "trend": "seasonal_pattern_detected",
                "trend_component": trend,
                "seasonal_component": seasonal,
                "strength_seasonality": strength,
            }
        slope = ExercisePrescription._linear_regression_slope(pyramid_timestamps, pyramid_1rms)
        return {
            "trend": "linear" if abs(slope) > 0.1 else "plateau",
            "slope": slope,
            "r_squared": ExercisePrescription._calculate_r_squared(pyramid_timestamps, pyramid_1rms),
        }

    @staticmethod
    def _pyramid_plateau_detection(
        pyramid_timestamps: List[float], pyramid_1rms: List[float]
    ) -> float:
        if len(pyramid_1rms) < 4:
            return 0.0
        change_points = ExercisePrescription._detect_change_points(pyramid_1rms)
        recent_var = np.var(pyramid_1rms[-4:]) / (
            np.mean(pyramid_1rms[-4:]) + ExercisePrescription.EPSILON
        )
        trend_score = (
            1.0
            if abs(
                ExercisePrescription._linear_regression_slope(
                    pyramid_timestamps[-4:], pyramid_1rms[-4:]
                )
            )
            < 0.5
            else 0.0
        )
        change_score = 1.0 if len(change_points) == 0 else 0.0
        plateau_score = 0.4 * trend_score + 0.3 * (1.0 if recent_var < 0.02 else 0.0) + 0.3 * change_score
        return plateau_score

    @staticmethod
    def _validate_pyramid_test(test: dict) -> bool:
        if test.get("max_achieved") and test.get("starting_weight"):
            if test["max_achieved"] > test["starting_weight"] * 1.5:
                return False
        sw = test.get("successful_weights") or []
        max_val = test.get("max_achieved") or (max(sw) if sw else 0.0)
        if any(w > max_val for w in sw):
            return False
        for a, b in zip(sw, sw[1:]):
            if b < a:
                return False
        return True

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
    def _arima_forecast(values: list[float], steps: int = 1) -> float:
        if len(values) < 3:
            return values[-1] if values else 0.0
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = ARIMA(values, order=(1, 1, 1))
                res = model.fit()
                pred = res.forecast(steps=steps)
                return float(pred[-1])
        except Exception:
            return float(values[-1])

    @staticmethod
    def _time_features(series: pd.Series) -> dict:
        lag1 = float(series.diff().iloc[-1]) if len(series) > 1 else 0.0
        ma7 = float(series.rolling(7, min_periods=1).mean().iloc[-1])
        ma30 = float(series.rolling(30, min_periods=1).mean().iloc[-1])
        roc = (
            float((series.iloc[-1] - series.iloc[-2]) / series.iloc[-2])
            if len(series) > 1 and series.iloc[-2] != 0
            else 0.0
        )
        dow = series.index[-1].dayofweek if len(series) > 0 else 0
        return {"lag1": lag1, "ma7": ma7, "ma30": ma30, "roc1": roc, "dow": dow}

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
        if len(w) == 0:
            return 0.0
        vol = w * r
        ewma = cls._ewma(vol, span=cls.L)
        return float(ewma[-1])

    @classmethod
    def _prev_load(cls, weights: list[float], reps: list[int]) -> float:
        w = np.array(weights)
        r = np.array(reps)
        vol = w * r
        if len(vol) == 0:
            return 0.0
        ewma = cls._ewma(vol, span=cls.L)
        if len(ewma) > cls.L:
            return float(ewma[-cls.L - 1])
        return float(ewma[0])

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

    @staticmethod
    def _prepare_series(values: list[float], timestamps: list[float], freq: str | None = None) -> pd.Series:
        if not values or not timestamps:
            return pd.Series(dtype=float)
        base = pd.Timestamp("1970-01-01")
        index = base + pd.to_timedelta(timestamps, unit="D")
        series = pd.Series(values, index=index).sort_index()
        if freq:
            series = series.resample(freq).mean()
        return series.interpolate(method="linear")

    @staticmethod
    def _weighted_slope(timestamps: list[float], weights: list[float], alpha: float = 0.3) -> float:
        if len(timestamps) < 2:
            return 0.0
        ser = ExercisePrescription._prepare_series(weights, timestamps)
        ew = ser.ewm(alpha=alpha, adjust=False).mean().values
        x = np.arange(len(ew))
        x_mean = np.mean(x)
        y_mean = np.mean(ew)
        num = np.sum((x - x_mean) * (ew - y_mean))
        den = np.sum((x - x_mean) ** 2)
        return float(num / den) if den != 0 else 0.0

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

    @staticmethod
    def _training_stress_balance(
        weights: list[float],
        reps: list[int],
        durations: list[float],
        timestamps: list[float],
        current_1rm: float,
    ) -> tuple[list[int], list[float]]:
        """Return Training Stress Balance values per day."""
        tss_list: list[float] = []
        for w, r, d in zip(weights, reps, durations):
            tss_val = ExercisePrescription._calculate_exercise_tss(
                [w],
                [r],
                [d],
                current_1rm,
            )
            tss_list.append(tss_val)

        daily: dict[int, float] = {}
        for t, val in zip(timestamps, tss_list):
            day = int(t)
            daily[day] = daily.get(day, 0.0) + val

        days = sorted(daily)
        loads = [daily[d] for d in days]
        tsb: list[float] = []
        for i, _ in enumerate(days):
            acute = np.mean(loads[max(0, i - 6) : i + 1])
            chronic = np.mean(loads[max(0, i - 27) : i + 1])
            tsb.append(acute - chronic)

        return days, tsb

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
    def _weekly_load_variability(weights: list[float], reps: list[int], times: list[float]) -> float:
        if not weights:
            return 0.0
        vols: dict[int, float] = {}
        for w, r, t in zip(weights, reps, times):
            week = int(t // 7)
            vols[week] = vols.get(week, 0.0) + w * r
        if len(vols) < 2:
            return 0.0
        values = np.array(list(vols.values()))
        mean = np.mean(values)
        std = np.std(values)
        return float(std / (mean + ExercisePrescription.EPSILON))

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

    # --- Enhanced algorithms ---
    NEUROMUSCULAR_DECAY: float = 0.85
    METABOLIC_DECAY: float = 0.95
    STRUCTURAL_DECAY: float = 0.90

    @staticmethod
    def _enhanced_fatigue(
        weights: list[float],
        reps: list[int],
        timestamps: list[float],
        target_reps: int,
    ) -> float:
        """Three-component fatigue model."""
        if not weights:
            return 0.0
        volumes = np.array(weights) * np.array(reps)
        t_current = timestamps[-1] if timestamps else 0
        t_arr = np.array(timestamps)
        neu = np.sum(volumes * (ExercisePrescription.NEUROMUSCULAR_DECAY ** (t_current - t_arr)))
        met = np.sum(volumes * (ExercisePrescription.METABOLIC_DECAY ** (t_current - t_arr)))
        struct = np.sum(volumes * (ExercisePrescription.STRUCTURAL_DECAY ** (t_current - t_arr)))
        if target_reps <= 5:
            total = 0.5 * neu + 0.3 * struct + 0.2 * met
        else:
            total = 0.3 * neu + 0.4 * struct + 0.3 * met
        return float(total)

    @staticmethod
    def _calculate_exercise_tss(
        weights: list[float],
        reps: list[int],
        durations: list[float],
        current_1rm: float,
    ) -> float:
        """Training Stress Score for resistance exercise."""
        tss_vals: list[float] = []
        for w, r, d in zip(weights, reps, durations):
            intensity_factor = w / current_1rm if current_1rm else 0.0
            if r <= 5:
                rep_factor = 1.0
            elif r <= 12:
                rep_factor = 0.8
            else:
                rep_factor = 0.6
            nl = intensity_factor * rep_factor
            dur_min = d / 60 if d else 1.0
            set_tss = (dur_min * nl * intensity_factor) / 60 * 100
            tss_vals.append(set_tss)
        return float(np.sum(tss_vals))

    @staticmethod
    def _tss_adjusted_fatigue(
        weights: list[float],
        reps: list[int],
        timestamps: list[float],
        durations: list[float],
        current_1rm: float,
    ) -> float:
        tss_values: list[float] = []
        if not weights:
            return 0.0
        t_current = timestamps[-1] if timestamps else 0
        for w, r, t, d in zip(weights, reps, timestamps, durations):
            set_tss = ExercisePrescription._calculate_exercise_tss([w], [r], [d], current_1rm)
            days_ago = t_current - t
            tss_values.append(set_tss * (0.9 ** days_ago))
        return float(np.sum(tss_values))

    @staticmethod
    def _session_rpe_adjustment(rpe_history: list[float], target_rpe_range: tuple = (7, 8)) -> float:
        """Load adjustment based on session RPE history."""
        if len(rpe_history) < 3:
            return 1.0
        recent = np.mean(rpe_history[-3:])
        target = np.mean(target_rpe_range)
        dev = (recent - target) / target
        if dev > 0.15:
            adj = 0.95 - (dev - 0.15) * 0.5
        elif dev < -0.15:
            adj = 1.05 + abs(dev + 0.15) * 0.3
        else:
            adj = 1.0
        return float(np.clip(adj, 0.85, 1.15))

    @staticmethod
    def _adjusted_volume_prescription(base_volume: float, rpe_history: list[float]) -> float:
        return base_volume * ExercisePrescription._session_rpe_adjustment(rpe_history)

    @staticmethod
    def _comprehensive_recovery_quality(
        sleep_hours: float | None,
        sleep_quality: float | None,
        calories: float | None,
        body_weight: float,
        stress_level: float | None = None,
        hrv_score: float | None = None,
    ) -> float:
        sleep_duration_factor = ExercisePrescription.clamp(1 + 0.06 * (sleep_hours - 8.0), 0.5, 1.1) if sleep_hours is not None else 1.0
        sleep_quality_factor = ExercisePrescription.clamp(0.5 + 0.12 * (sleep_quality / 5), 0.5, 1.1) if sleep_quality is not None else 1.0
        sleep_component = math.sqrt(sleep_duration_factor * sleep_quality_factor)
        ea_component = ExercisePrescription.clamp((calories / (body_weight * 0.85)) / 40.0, 0.5, 1.1) if calories is not None else 1.0
        stress_component = ExercisePrescription.clamp(1.0 - (stress_level / 10) * 0.3, 0.7, 1.0) if stress_level is not None else 1.0
        hrv_component = ExercisePrescription.clamp(hrv_score / 50, 0.8, 1.2) if hrv_score is not None else 1.0
        recovery_quality = (
            0.4 * sleep_component
            + 0.3 * ea_component
            + 0.2 * stress_component
            + 0.1 * hrv_component
        )
        return float(recovery_quality)

    @staticmethod
    def _adaptive_periodization_factor(performance_trend: list[float], weeks_in_phase: int, target_phase_length: int = 4) -> float:
        if len(performance_trend) < 3:
            return 0.7
        x = np.arange(len(performance_trend))
        slope = np.polyfit(x, performance_trend, 1)[0]
        mean_perf = np.mean(performance_trend)
        normalized_slope = slope / mean_perf if mean_perf > 0 else 0
        phase_progress = weeks_in_phase / target_phase_length
        if normalized_slope > 0.02:
            adaptive_factor = 0.8 + 0.2 * (1 - phase_progress)
        elif normalized_slope < -0.01:
            adaptive_factor = 0.6 + 0.4 * phase_progress
        else:
            adaptive_factor = 0.7 + 0.3 * phase_progress
        return ExercisePrescription.clamp(adaptive_factor, 0.5, 1.0)

    @staticmethod
    def _periodized_volume_prescription(base_volume: float, performance_trend: list[float], weeks_in_phase: int) -> float:
        factor = ExercisePrescription._adaptive_periodization_factor(performance_trend, weeks_in_phase)
        return base_volume * factor

    @staticmethod
    def _estimate_velocity_loss(set_number: int, target_reps: int, intensity_factor: float, fatigue_level: float) -> float:
        base_loss_per_rep = 0.05 if intensity_factor > 0.85 else 0.03
        fatigue_multiplier = 1.0 + (fatigue_level / 1000) * 0.5
        set_multiplier = 1.0 + (set_number - 1) * 0.1
        est = base_loss_per_rep * target_reps * fatigue_multiplier * set_multiplier
        return float(min(est, 0.4))

    @staticmethod
    def _velocity_adjusted_reps(base_reps: int, set_number: int, intensity_factor: float, fatigue_level: float, target_velocity_loss: float) -> int:
        est_loss = ExercisePrescription._estimate_velocity_loss(set_number, base_reps, intensity_factor, fatigue_level)
        if est_loss > target_velocity_loss:
            reduction = target_velocity_loss / est_loss
            adjusted = int(base_reps * reduction)
            return max(adjusted, 1)
        return base_reps

    @staticmethod
    def _comprehensive_deload_assessment(
        performance_decline: float,
        rpe_elevation: float,
        volume_tolerance: float,
        recovery_quality: float,
        weeks_since_deload: int,
    ) -> float:
        perf_score = min(performance_decline * 2, 1.0)
        rpe_score = max(0.0, (rpe_elevation - 1.0) / 2.0)
        volume_score = max(0.0, (1.0 - volume_tolerance) * 1.5)
        recovery_score = max(0.0, (1.0 - recovery_quality) * 1.2)
        time_score = min(weeks_since_deload / 4.0, 1.0)
        return 0.30 * perf_score + 0.25 * rpe_score + 0.20 * volume_score + 0.15 * recovery_score + 0.10 * time_score

    @staticmethod
    def _deload_adjusted_prescription(base_prescription: list[dict], deload_score: float) -> list[dict]:
        if deload_score > 0.7:
            vol_red, int_red = 0.6, 0.8
        elif deload_score > 0.5:
            vol_red, int_red = 0.75, 0.9
        else:
            vol_red, int_red = 1.0, 1.0
        adjusted: list[dict] = []
        for s in base_prescription:
            new_set = s.copy()
            new_set["reps"] = int(new_set["reps"] * vol_red)
            new_set["weight"] = new_set["weight"] * int_red
            adjusted.append(new_set)
        return adjusted

    @staticmethod
    def _autoregulated_volume_prescription(base_volume: float, recent_performance: float, recovery_quality: float, ac_ratio: float, rpe_consistency: float) -> float:
        performance_factor = ExercisePrescription.clamp(recent_performance, 0.7, 1.3)
        recovery_factor = ExercisePrescription.clamp(recovery_quality, 0.6, 1.2)
        ac_factor = ExercisePrescription.clamp(2.0 - ac_ratio, 0.8, 1.2)
        consistency_factor = ExercisePrescription.clamp(1.0 - rpe_consistency, 0.9, 1.1)
        mult = 0.35 * performance_factor + 0.30 * recovery_factor + 0.25 * ac_factor + 0.10 * consistency_factor
        return base_volume * ExercisePrescription.clamp(mult, 0.6, 1.4)

    @staticmethod
    def _advanced_plateau_detection(performance_values: list[float], timestamps: list[float], rpe_values: list[float], volume_values: list[float]) -> float:
        if len(performance_values) < 6:
            return 0.0
        x = np.arange(len(performance_values))
        performance_slope = np.polyfit(x, performance_values, 1)[0]
        performance_score = 1.0 if abs(performance_slope) < 0.001 else 0.0
        rpe_trend = np.polyfit(x, rpe_values, 1)[0]
        rpe_score = 1.0 if rpe_trend > 0.1 else 0.0
        efficiency = []
        for i in range(1, len(performance_values)):
            if volume_values[i] > 0:
                eff = (performance_values[i] - performance_values[i-1]) / volume_values[i]
                efficiency.append(eff)
        efficiency_score = 1.0 if efficiency and np.mean(efficiency) < 0.001 else 0.0
        recent_cv = np.std(performance_values[-4:]) / np.mean(performance_values[-4:]) * 100
        variability_score = 1.0 if recent_cv < 2.0 else 0.0
        return 0.4 * performance_score + 0.3 * rpe_score + 0.2 * efficiency_score + 0.1 * variability_score

    @staticmethod
    def _stress_level(weights: list[float], reps: list[int], rpe_scores: list[float], times: list[float], current_1rm: float, mev: float, sessions: int = 3) -> float:
        if not weights:
            return 0.0
        by_day: dict[int, list[tuple[float, float]]] = {}
        for w, r, rpe, t in zip(weights, reps, rpe_scores, times):
            day = int(t)
            by_day.setdefault(day, []).append((w, rpe, r))
        sss_values: list[float] = []
        for day in sorted(by_day.keys()):
            entries = by_day[day]
            vol = sum(w * r for w, _rpe, r in entries)
            weights_day = [w for w, _rpe, _ in entries]
            rpe_day = [rp for _w, rp, _ in entries]
            intensity_factor = ExercisePrescription.clamp(np.mean(weights_day) / current_1rm, 0.6, 1.1)
            rpe_factor = ExercisePrescription.clamp(np.mean(rpe_day) / 7, 0.8, 1.3)
            sss_values.append(vol * intensity_factor * rpe_factor)
        recent = sss_values[-sessions:]
        stress = np.mean(recent) / mev if mev else np.mean(recent)
        return ExercisePrescription.clamp(stress, 0.0, 2.0)

    @staticmethod
    def _compute_target_velocity_loss(base_reps: int, last_rpe: float, last_reps: int, intensity_factor: float, fatigue_ratio: float) -> float:
        if base_reps <= 5:
            base = 0.10
        elif base_reps <= 12:
            base = 0.18
        else:
            base = 0.25
        loss = base
        if last_rpe >= 9:
            loss -= 0.02
        if last_rpe <= 7 and last_reps >= base_reps:
            loss += 0.03
        if fatigue_ratio > 0.7:
            loss -= 0.03
        return ExercisePrescription.clamp(loss, 0.08, 0.35)

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
        stress_levels: list[float] | None = None,
        hrv_scores: list[float] | None = None,
        weeks_in_phase: int = 1,
        weeks_since_deload: int = 0,
        target_1rm: float | None = None,
        days_remaining: int | None = None,
        decay: float = 0.9,
        theta: float = 0.1,
        stress: float = 0.1,
        phase_factor: float = 0.7,
        target_velocity_loss: float | None = None,
        exercise_name: str | None = None,
    ) -> dict:
        """Return a detailed workout prescription."""

        series_w = cls._prepare_series(weights, timestamps)
        series_r = cls._prepare_series(reps, timestamps)
        series_rpe = cls._prepare_series(rpe_scores, timestamps)

        current_1rm_calc = cls._current_1rm(list(series_w), list(series_r))
        ts_list = [(t - series_w.index[0]).days for t in series_w.index]
        pyr_ts, pyr_vals, pyr_weights, pyr_metrics = cls._process_pyramid_tests(
            exercise_name
        )
        current_1rm = cls._enhanced_1rm_calculation(
            list(series_w),
            list(series_r),
            pyr_ts,
            pyr_vals,
            ts_list[-1] if ts_list else 0,
        )
        total_volume = cls._total_volume(list(series_w), list(series_r))
        t_mean = cls._means(list(series_w.index.map(lambda t: (t - series_w.index[0]).days)))
        y_mean = cls._means(list(series_w))
        slope = cls._weighted_slope(ts_list, list(series_w))
        recent_load = cls._recent_load(list(series_w), list(series_r))
        prev_load = cls._prev_load(list(series_w), list(series_r))
        thresh = cls._threshold(recent_load, prev_load)
        cv = cls._cv(list(series_w), list(series_r))
        plateau = cls._plateau(slope, cv, thresh, list(series_w), ts_list)
        volume_per_set = list(np.array(weights) * np.array(reps))
        adv_plateau = cls._advanced_plateau_detection(list(series_w), ts_list, rpe_scores, volume_per_set)
        plateau = (plateau + adv_plateau) / 2
        feats = cls._time_features(series_w)
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
        base_fatigue = cls._pyramid_enhanced_fatigue(
            pyr_ts,
            pyr_vals,
            pyr_weights,
            pyr_metrics,
            base_fatigue,
            ts_list[-1] if ts_list else 0,
        )
        target_reps_est = int(round(np.mean(reps))) if reps else 8
        enhanced_fatigue = cls._enhanced_fatigue(weights, reps, ts_list, target_reps_est)
        tss_fatigue = cls._tss_adjusted_fatigue(
            weights,
            reps,
            ts_list,
            durations if durations is not None else [50.0 for _ in reps],
            current_1rm,
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

        fatigue = base_fatigue + recovery_fatigue + enhanced_fatigue + tss_fatigue
        ac_ratio = cls._ac_ratio(list(series_w), list(series_r))
        perf_scores = cls._performance_scores_from_logs(list(series_w), list(series_r), ts_list, MEV)
        rec_scores = cls._recovery_scores_from_logs(
            body_weight, calories, sleep_hours, sleep_quality
        )
        ea = cls._energy_availability(body_weight, np.mean(calories) if calories else None)
        stress_auto = cls._stress_level(weights, reps, rpe_scores, ts_list, current_1rm, MEV)
        mrv = cls._mrv(MEV, fatigue, stress_auto, ea, theta)
        sri = cls._sleep_recovery_index(
            np.mean(sleep_hours) if sleep_hours else None,
            np.mean(sleep_quality) if sleep_quality else None,
        )
        adj_mrv = cls._adj_mrv(mrv, perf_scores, rec_scores)
        avg_sleep = np.mean(sleep_hours) if sleep_hours else None
        avg_quality = np.mean(sleep_quality) if sleep_quality else None
        avg_cal = np.mean(calories) if calories else None
        stress_val = np.mean(stress_levels) if stress_levels else stress_auto
        hrv_val = np.mean(hrv_scores) if hrv_scores else None
        recovery_quality = cls._comprehensive_recovery_quality(
            avg_sleep, avg_quality, avg_cal, body_weight, stress_val, hrv_val
        )
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
            forecast_var = cls._var_forecast(session_volumes, [1] * len(session_volumes))
            forecast_arima = cls._arima_forecast(session_volumes)
            vol_presc = (vol_presc + forecast_var + forecast_arima) / 3
        vol_presc = cls._periodized_volume_prescription(vol_presc, list(series_w), weeks_in_phase)
        rpe_consistency = np.std(rpe_scores) / (np.mean(rpe_scores) + cls.EPSILON) if rpe_scores else 0.0
        perf_factor = np.mean(np.array(perf_scores)) if len(perf_scores) > 0 else 1.0
        vol_presc = cls._autoregulated_volume_prescription(vol_presc, perf_factor if perf_scores else 1.0, recovery_quality, ac_ratio, rpe_consistency)
        vol_presc = cls._adjusted_volume_prescription(vol_presc, rpe_scores)

        if pyr_vals:
            prog_adj = cls._pyramid_enhanced_progression(
                pyr_ts,
                pyr_vals,
                target_1rm,
                days_remaining,
            )
            urgency_mod = cls.clamp(1 + prog_adj, 0.5, 2.0)
        else:
            urgency_mod = 1.0

        if pyr_vals:
            pyr_1rm_last = pyr_vals[-1]
            days_since_pyr = (ts_list[-1] - pyr_ts[-1]) if ts_list else 0
            cv_slice = pyr_vals[-min(5, len(pyr_vals)) :]
            cv_pyr = np.std(cv_slice) / (np.mean(cv_slice) + cls.EPSILON)
            recency = 1 / (1 + math.exp((days_since_pyr - 7) / 3))
            reliab = cls.clamp(1 - cv_pyr, 0.6, 1.0)
            sample = cls.clamp(math.log1p(len(pyr_vals)) / math.log1p(10), 0.3, 1.0)
            fatigue_ratio = cls.clamp(base_fatigue / (adj_mrv + cls.EPSILON), 0.6, 1.4)
            fatigue_corr = 1 / fatigue_ratio
            w_pyr = cls.clamp(0.8 * recency * reliab * sample * fatigue_corr, 0.2, 0.8)
            current_1rm = w_pyr * pyr_1rm_last + (1 - w_pyr) * current_1rm_calc

        urgency = cls._urgency(target_1rm, current_1rm) * urgency_mod
        delta_1rm, delta_vol = cls._deltas(current_1rm, y_mean, recent_load, prev_load)
        rec_factor = np.mean(np.array(rec_scores)) if len(rec_scores) > 0 else 1.0
        rec_factor = (rec_factor + recovery_quality) / 2
        alpha = cls._alpha(delta_1rm, delta_vol, rec_factor, list(series_w), experience)
        alpha = cls._pyramid_enhanced_alpha(
            alpha,
            pyr_ts,
            pyr_vals,
            pyr_weights,
            pyr_metrics,
            ts_list[-1] if ts_list else 0,
        )
        required_rate = cls._required_rate(target_1rm, current_1rm, days_remaining)
        achievement_prob = cls._achievement_probability(required_rate)
        weekly_rate = cls._weekly_rate(slope, y_mean)
        weekly_monotony = cls._weekly_monotony(list(series_w), list(series_r))
        tut_ratio = (
            float(np.sum(durations)) / (50.0 * len(durations)) if durations else 1.0
        )
        deload_trigger = cls._deload_trigger(perf_factor, rpe_scores, rec_factor, tut_ratio)
        rpe_scale = cls._rpe_scale(rpe_scores, durations, 50.0)
        confidence_int = cls._confidence_interval(slope, list(series_w), ts_list)
        deload_score = cls._comprehensive_deload_assessment(
            1 - perf_factor,
            np.mean(rpe_scores[-3:]) / 7 if rpe_scores else 1.0,
            ac_ratio,
            recovery_quality,
            weeks_since_deload,
        )

        mean_vol = np.mean(np.array(series_w) * np.array(series_r)) if len(series_w) > 0 else 1.0
        vol_factor = cls.clamp(math.log1p(total_volume) / 8, 0.95, 1.05)
        forecast_weight = cls._arima_forecast(list(series_w))
        trend_mod = cls.clamp(
            series_w.iloc[-1] / (forecast_weight + cls.EPSILON),
            0.9,
            1.1,
        )
        roc_mod = 1 + feats["roc1"]
        season_mod = 1 + 0.01 * math.sin(2 * math.pi * feats["dow"] / 7)
        vol_factor *= trend_mod * roc_mod * season_mod
        last_t = ts_list[-1] if ts_list else 0.0
        time_factor = cls.clamp(
            1 + (last_t - t_mean) / (10 * (last_t + cls.EPSILON)),
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
        wave_low, wave_mid, wave_high = cls._wavelet_energy(list(series_w))
        intensity_target = (0.75 if base_reps >= 6 else 0.85) * (
            1 + wave_high / (wave_low + wave_mid + 1e-9) * 0.01
        )

        sets_prescription: list[dict] = []
        fatigue_ratio = fatigue / (adj_mrv + cls.EPSILON)
        if target_velocity_loss is None:
            last_rpe = rpe_scores[-1] if rpe_scores else 8.0
            last_reps = reps[-1] if reps else base_reps
            intensity_factor_last = (weights[-1] / current_1rm) if weights else 0.8
            target_velocity_loss = cls._compute_target_velocity_loss(
                base_reps,
                last_rpe,
                last_reps,
                intensity_factor_last,
                fatigue_ratio,
            )
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
                0.95 * max(current_1rm, forecast_weight),
            )
            if deload_needed:
                weight_k *= 0.8
            reps_k = cls._velocity_adjusted_reps(int(reps_k), k, weight_k / current_1rm, fatigue, target_velocity_loss)
            target_rpe = cls.clamp(7 + 0.3 * plateau, 6, 9)
            rest_corr = 0.0
            if durations is not None:
                _, rest_corr = cls._cross_correlation(durations, rpe_scores, max_lag=1)
            rest_k = (90 + 30 * rpe_scale + 15 * (reps_k < 5) + 10 * k) * (
                1 + 0.1 * rest_corr
            )
            sets_prescription.append(
                {
                    "set": k,
                    "reps": int(reps_k),
                    "weight": round(weight_k, 1),
                    "target_rpe": round(target_rpe, 1),
                    "rest_seconds": int(rest_k),
                }
            )
        if deload_score > 0.5:
            sets_prescription = cls._deload_adjusted_prescription(sets_prescription, deload_score)

        pyramid_trend = cls._analyze_1rm_trends(pyr_ts, pyr_vals)
        pyramid_plateau = cls._pyramid_plateau_detection(pyr_ts, pyr_vals)

        result = {
            "prescription": sets_prescription,
            "total_sets": N,
            "deload_recommended": deload_needed,
            "analysis": {
                "current_1RM": round(current_1rm, 1),
                "plateau_score": round(plateau, 2),
                "pyramid_plateau": round(pyramid_plateau, 2),
                "fatigue_level": round(fatigue / 1000, 2),
                "progression_modifier": round(alpha, 3),
                "urgency_factor": round(urgency, 2),
                "achievement_probability": round(achievement_prob, 2),
                "ac_ratio": round(ac_ratio, 2),
                "weekly_monotony": round(weekly_monotony, 2),
                "deload_trigger": round(deload_trigger, 2),
                "pyramid_trend": pyramid_trend,
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
