import os
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))

class VoiceCommandTest(unittest.TestCase):
    def test_script_included(self) -> None:
        path = os.path.join(ROOT, "streamlit_app.py")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("startVoiceCommand()", content)

