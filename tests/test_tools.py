import os
import sys
import math
import unittest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from tools import MathTools, ExercisePrescription
from db import PyramidTestRepository, PyramidEntryRepository


class MathToolsTestCase(unittest.TestCase):
    def test_constants(self) -> None:
        self.assertAlmostEqual(MathTools.EPL_COEFF, 0.0333)
        self.assertAlmostEqual(MathTools.ALPHA_MIN, 0.75)
        self.assertAlmostEqual(MathTools.ALPHA_MAX, 1.0)
        self.assertAlmostEqual(MathTools.FFM_FRACTION, 0.407)
        self.assertAlmostEqual(MathTools.EA_BASELINE, 1.097)
        self.assertEqual(MathTools.L, 3)
        self.assertAlmostEqual(MathTools.W1, 0.4)
        self.assertAlmostEqual(MathTools.W2, 0.3)
        self.assertAlmostEqual(MathTools.W3, 0.3)

    def test_clamp(self) -> None:
        self.assertEqual(MathTools.clamp(5, 0, 10), 5)
        self.assertEqual(MathTools.clamp(-1, 0, 10), 0)
        self.assertEqual(MathTools.clamp(11, 0, 10), 10)
        with self.assertRaises(ValueError):
            MathTools.clamp(1, 2, 1)

    def test_epley_1rm(self) -> None:
        self.assertAlmostEqual(MathTools.epley_1rm(100, 5), 100 * (1 + 0.0333 * 5))
        self.assertAlmostEqual(MathTools.epley_1rm(100, 10), 100 * (1 + 0.0333 * 8))
        self.assertAlmostEqual(MathTools.epley_1rm(100, 5, factor=1.1), 100 * (1 + 0.0333 * 5) * 1.1)
        with self.assertRaises(ValueError):
            MathTools.epley_1rm(100, -1)

    def test_volume(self) -> None:
        sets = [(10, 100.0), (5, 150.0)]
        self.assertEqual(MathTools.volume(sets), 10 * 100.0 + 5 * 150.0)
        self.assertEqual(MathTools.volume([]), 0.0)

    def test_experience_score(self) -> None:
        self.assertEqual(MathTools.experience_score(12, 5), 60)
        with self.assertRaises(ValueError):
            MathTools.experience_score(-1, 5)

    def test_basic_threshold(self) -> None:
        self.assertAlmostEqual(MathTools.basic_threshold(105.0, 100.0), 0.05)
        with self.assertRaises(ValueError):
            MathTools.basic_threshold(100.0, 0.0)

    def test_required_progression(self) -> None:
        self.assertAlmostEqual(MathTools.required_progression(150.0, 120.0, 30), 1.0)
        with self.assertRaises(ValueError):
            MathTools.required_progression(150.0, 120.0, 0)

    def test_warmup_weights(self) -> None:
        weights = MathTools.warmup_weights(100.0, 3)
        self.assertEqual(weights, [30.0, 60.0, 90.0])
        with self.assertRaises(ValueError):
            MathTools.warmup_weights(-1.0, 3)

    def test_session_density(self) -> None:
        val = MathTools.session_density(1000.0, 600)
        self.assertAlmostEqual(val, 100.0)

    def test_sleep_recovery_index(self) -> None:
        sf = ExercisePrescription._sleep_factor(7)
        psqf = ExercisePrescription._perceived_sleep_quality_factor(4)
        self.assertAlmostEqual(sf, 0.94)
        self.assertAlmostEqual(psqf, 0.98)
        sri = ExercisePrescription._sleep_recovery_index(7, 4)
        self.assertAlmostEqual(sri, math.sqrt(sf * psqf))

    def test_time_series_utils(self) -> None:
        ewma = ExercisePrescription._ewma([1, 2, 3, 4], span=2)
        self.assertAlmostEqual(ewma[-1], 3.5185, places=3)
        ar = ExercisePrescription._ar_decay([1, 2, 3, 4, 5])
        self.assertAlmostEqual(ar, 1.0, places=3)
        lag, corr = ExercisePrescription._cross_correlation(
            [1, 2, 3, 4, 5], [0, 0, 1, 2, 3], max_lag=2
        )
        self.assertEqual(lag, -2)
        self.assertAlmostEqual(corr, 1.0)
        trend, seasonal = ExercisePrescription._seasonal_components(
            [1, 2, 3, 4, 5, 6, 7, 1, 2, 3, 4, 5, 6, 7], 7
        )
        self.assertAlmostEqual(trend[-1], 4.0, places=1)
        self.assertAlmostEqual(seasonal[-1], 3.0, places=1)
        cp = ExercisePrescription._change_point(
            [100, 102, 104, 105, 105, 105, 105], [0, 1, 2, 3, 4, 5, 6]
        )
        self.assertEqual(cp, 3)
        var_pred = ExercisePrescription._var_forecast([100, 101, 102, 103, 104], [5, 5, 5, 5, 5])
        self.assertAlmostEqual(var_pred, 105.0)
        kalman = ExercisePrescription._kalman_filter([1, 2, 3, 2, 2])
        self.assertAlmostEqual(kalman[-1], 2.22, places=2)
        wave = ExercisePrescription._wavelet_energy([1, 2, 3, 4, 5, 6, 7, 8])
        self.assertAlmostEqual(wave[0], 194.0, places=1)
        anomaly = ExercisePrescription._anomaly_score([1, 2, 100, 3])
        self.assertGreater(anomaly, 0.5)

    def test_enhanced_algorithms(self) -> None:
        fatigue = ExercisePrescription._enhanced_fatigue(
            [100, 110],
            [5, 5],
            [0, 1],
            5,
            [8, 8],
        )
        self.assertAlmostEqual(fatigue, 1091.75, places=2)
        tss = ExercisePrescription._calculate_exercise_tss([100.0], [5], [60], 120.0)
        self.assertAlmostEqual(tss, 1.157, places=3)
        stress = ExercisePrescription._stress_level([100, 110], [5, 5], [8, 8], [0, 1], 120.0, 10)
        self.assertAlmostEqual(stress, 2.0)

    def test_readiness_score(self) -> None:
        val = MathTools.readiness_score(2.0, 3.0)
        expected = MathTools.clamp(10.0 - math.sqrt(2.0**2 + 3.0**2), 0.0, 10.0)
        self.assertAlmostEqual(val, expected)

    def test_weighted_fusion_with_reliability(self) -> None:
        result = MathTools.weighted_fusion(5.0, 0.3, 8.0, algo_conf=0.7, algo_reliability=0.5)
        mc = 0.3
        ac = 0.7 * 0.5
        expected = ((mc**2) / (mc**2 + ac**2)) * 5.0 + ((ac**2) / (mc**2 + ac**2)) * 8.0
        self.assertAlmostEqual(result, expected)

    def test_periodization_and_velocity_loss(self) -> None:
        factor = ExercisePrescription._adaptive_periodization_factor([1.0, 1.1, 1.2, 1.3], 2)
        self.assertAlmostEqual(factor, 0.9)

        loss = ExercisePrescription._compute_target_velocity_loss(8, 9.0, 8, 0.75, 0.8)
        self.assertAlmostEqual(loss, 0.13, places=2)

    def test_exercise_prescription(self) -> None:
        weights = [100.0, 105.0, 110.0, 112.5, 115.0]
        reps = [5, 5, 5, 5, 5]
        timestamps = [0, 7, 14, 21, 28]
        rpe = [8, 8, 8, 8, 8]
        durations = [45, 46, 44, 47, 48]
        calories = [2720, 2720, 2720, 2720, 2176]
        sleep_hours = [8, 8, 8, 8, 8]
        sleep_quality = [4, 4, 4, 4, 4]
        rest_times = [240, 240, 240, 240, 240]

        result = ExercisePrescription.exercise_prescription(
            weights,
            reps,
            timestamps,
            rpe,
            durations=durations,
            rest_times=rest_times,
            body_weight=80.0,
            months_active=12,
            workouts_per_month=8,
            calories=calories,
            sleep_hours=sleep_hours,
            sleep_quality=sleep_quality,
            target_1rm=140.0,
            days_remaining=30,
        )

        self.assertIsInstance(result["total_sets"], int)
        first_set = result["prescription"][0]
        self.assertIsInstance(first_set["reps"], int)
        self.assertIsInstance(first_set["weight"], float)

    def test_pyramid_weighting(self) -> None:
        weights = [100.0, 105.0, 110.0, 112.5, 115.0]
        reps = [5, 5, 5, 5, 5]
        timestamps = [0, 7, 14, 21, 28]
        rpe = [8, 8, 8, 8, 8]

        repo_t = PyramidTestRepository()
        repo_e = PyramidEntryRepository()
        repo_t._delete_all("pyramid_tests")
        repo_e._delete_all("pyramid_entries")
        base = ExercisePrescription.exercise_prescription(
            weights,
            reps,
            timestamps,
            rpe,
            body_weight=80.0,
            months_active=12,
            workouts_per_month=8,
        )
        base_rm = base["analysis"]["current_1RM"]
        tid = repo_t.create("2023-01-01")
        repo_e.add(tid, 130.0)
        result = ExercisePrescription.exercise_prescription(
            weights,
            reps,
            timestamps,
            rpe,
            body_weight=80.0,
            months_active=12,
            workouts_per_month=8,
        )
        repo_t._delete_all("pyramid_tests")
        repo_e._delete_all("pyramid_entries")
        enhanced_rm = result["analysis"]["current_1RM"]
        self.assertNotEqual(enhanced_rm, base_rm)

    def test_pyramid_progression_metrics(self) -> None:
        metrics = ExercisePrescription._pyramid_progression_metrics([100.0, 110.0, 120.0])
        self.assertAlmostEqual(metrics["increment_coeff"], 0.0, places=1)
        self.assertGreater(metrics["efficiency_score"], 1.0)
        self.assertAlmostEqual(metrics["strength_reserve"], (120.0 - 110.0) / 110.0, places=2)

    def test_pyramid_trend_and_plateau(self) -> None:
        ts = [0, 7, 14, 21, 28]
        rms = [100.0, 105.0, 110.0, 112.5, 115.0]
        trend = ExercisePrescription._analyze_1rm_trends(ts, rms)
        self.assertEqual(trend["trend"], "linear")
        plateau = ExercisePrescription._pyramid_plateau_detection(ts, rms)
        self.assertLessEqual(plateau, 1.0)

    def test_pyramid_series_metrics(self) -> None:
        repo_t = PyramidTestRepository()
        repo_e = PyramidEntryRepository()
        repo_t._delete_all("pyramid_tests")
        repo_e._delete_all("pyramid_entries")
        tid1 = repo_t.create("2023-01-01")
        repo_e.add(tid1, 100.0)
        repo_e.add(tid1, 110.0)
        tid2 = repo_t.create("2023-01-08")
        repo_e.add(tid2, 105.0)
        repo_e.add(tid2, 115.0)
        ts, rms, weights, metrics = ExercisePrescription._process_pyramid_tests()
        self.assertEqual(len(ts), 2)
        self.assertIn("strength_reserve", metrics[0])
        fatigue = ExercisePrescription._pyramid_enhanced_fatigue(
            ts,
            rms,
            weights,
            metrics,
            1000.0,
            ts[-1],
        )
        alpha = ExercisePrescription._pyramid_enhanced_alpha(
            0.05,
            ts,
            rms,
            weights,
            metrics,
            ts[-1],
        )
        repo_t._delete_all("pyramid_tests")
        repo_e._delete_all("pyramid_entries")
        self.assertAlmostEqual(fatigue, 1000.0)
        self.assertAlmostEqual(alpha, 0.051, places=3)

    def test_validate_pyramid_test(self) -> None:
        test = {
            "starting_weight": 100.0,
            "successful_weights": [100.0, 110.0, 120.0],
            "failed_weight": 125.0,
            "max_achieved": 120.0,
        }
        self.assertTrue(ExercisePrescription._validate_pyramid_test(test))
        test_bad = {
            "starting_weight": 100.0,
            "successful_weights": [120.0, 110.0],
            "failed_weight": 140.0,
            "max_achieved": 120.0,
        }
        self.assertFalse(ExercisePrescription._validate_pyramid_test(test_bad))


if __name__ == '__main__':
    unittest.main()
