import os
import sys
import math
import unittest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from tools import MathTools, ExercisePrescription


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

    def test_sleep_recovery_index(self) -> None:
        sf = ExercisePrescription._sleep_factor(7)
        psqf = ExercisePrescription._perceived_sleep_quality_factor(4)
        self.assertAlmostEqual(sf, 0.94)
        self.assertAlmostEqual(psqf, 0.98)
        sri = ExercisePrescription._sleep_recovery_index(7, 4)
        self.assertAlmostEqual(sri, math.sqrt(sf * psqf))

    def test_exercise_prescription(self) -> None:
        weights = [100.0, 105.0, 110.0, 112.5, 115.0]
        reps = [5, 5, 5, 5, 5]
        timestamps = [0, 7, 14, 21, 28]
        rpe = [8, 8, 8, 8, 8]
        calories = [2720, 2720, 2720, 2720, 2176]
        sleep_hours = [8, 8, 8, 8, 8]
        sleep_quality = [4, 4, 4, 4, 4]

        result = ExercisePrescription.exercise_prescription(
            weights,
            reps,
            timestamps,
            rpe,
            body_weight=80.0,
            months_active=12,
            workouts_per_month=8,
            calories=calories,
            sleep_hours=sleep_hours,
            sleep_quality=sleep_quality,
            target_1rm=140.0,
            days_remaining=30,
        )

        self.assertEqual(result["total_sets"], 1)
        first_set = result["prescription"][0]
        self.assertEqual(first_set["reps"], 1)
        self.assertAlmostEqual(first_set["weight"], 108.4)


if __name__ == '__main__':
    unittest.main()
