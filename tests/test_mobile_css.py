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
        self.assertIn("max-width: 1024px", content)
        self.assertIn(
            "@media screen and (max-width: 1024px) and (orientation: landscape)",
            content,
        )
        self.assertIn("orientation: landscape", content)
        self.assertIn("textarea,", content)
        self.assertIn("Math.min", content)
        self.assertIn("@media screen and (max-width: 320px)", content)
        self.assertIn("font-size: 0.95rem;", content)
        self.assertIn(".bottom-nav", content)
        self.assertIn("repeat(5, 1fr)", content)
        self.assertIn("repeat(6, 1fr)", content)
        self.assertIn(
            "@media screen and (max-width: 375px) and (orientation: portrait)",
            content,
        )
        self.assertIn("font-size: 0.65rem;", content)
        self.assertIn(".scroll-top", content)
        self.assertIn(".metric-card", content)
        self.assertIn("handleTouchStart", content)
        self.assertIn("scrollY", content)
        self.assertIn("addEventListener('input', saveScroll", content)
        self.assertIn("addEventListener('change', saveScroll", content)
        self.assertIn("addEventListener('click', saveScroll", content)
        self.assertNotIn("persistExpanders()", content)
        self.assertNotIn("dataset.expKey", content)
        self.assertIn(
            "div[data-testid=\"stTabs\"] div[data-testid=\"stTabs\"] > div:first-child",
            content,
        )
        self.assertIn("dlg.addEventListener('touchstart'", content)
        self.assertIn("dlg.addEventListener('touchend'", content)

if __name__ == "__main__":
    unittest.main()
