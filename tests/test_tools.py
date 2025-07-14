import os
import sys
import unittest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from tools import MathTools


class MathToolsTestCase(unittest.TestCase):
    def test_constants(self) -> None:
        self.assertAlmostEqual(MathTools.EPL_COEFF, 0.0333)
        self.assertAlmostEqual(MathTools.ALPHA_MIN, 0.75)
        self.assertAlmostEqual(MathTools.ALPHA_MAX, 1.0)
        self.assertAlmostEqual(MathTools.FFM_FRACTION, 0.407)
        self.assertAlmostEqual(MathTools.EA_BASELINE, 1.097)

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


if __name__ == '__main__':
    unittest.main()
