import unittest
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from pythonista_app import EnvironmentDetector


class EnvironmentTestCase(unittest.TestCase):
    def test_not_pythonista(self) -> None:
        self.assertFalse(EnvironmentDetector.is_pythonista())


if __name__ == "__main__":
    unittest.main()
