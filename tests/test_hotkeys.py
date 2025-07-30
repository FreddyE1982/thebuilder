import os
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))

class HotkeyScriptTest(unittest.TestCase):
    def test_hotkey_script_present(self) -> None:
        path = os.path.join(ROOT, "streamlit_app.py")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("handleHotkeys", content)
        self.assertIn("window.addEventListener('keydown'", content)
        self.assertIn("tabKeys", content)
        self.assertIn("addSetKey", content)
        self.assertIn("toggleThemeKey", content)

if __name__ == "__main__":
    unittest.main()
