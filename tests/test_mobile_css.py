import os
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))

class MobileCSSTest(unittest.TestCase):
    def test_css_rules_present(self) -> None:
        path = os.path.join(ROOT, "streamlit_app.py")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("div[data-testid=\"stSidebar\"]", content)
        self.assertIn("font-size: 1.75rem;", content)
        self.assertIn("font-size: 1.5rem;", content)
        self.assertIn("font-size: 1.25rem;", content)
        self.assertIn("orientation: landscape", content)
        self.assertIn("textarea,", content)

if __name__ == "__main__":
    unittest.main()
