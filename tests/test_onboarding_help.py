import os
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))

class OnboardingHelpTest(unittest.TestCase):
    def test_help_methods_present(self) -> None:
        path = os.path.join(ROOT, "streamlit_app.py")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("_new_feature_onboarding", content)
        self.assertIn("_first_workout_tutorial", content)
        self.assertIn("_show_help_tip", content)
        self.assertIn("_show_completion_animation", content)

if __name__ == "__main__":
    unittest.main()
