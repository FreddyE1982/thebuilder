import os
import unittest
from streamlit.testing.v1 import AppTest

class MobileLayoutPerTabTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = "test_mobile.db"
        self.yaml_path = "test_mobile.yaml"
        os.environ["DB_PATH"] = self.db_path
        os.environ["YAML_PATH"] = self.yaml_path
        os.environ["TEST_MODE"] = "1"
        self.at = AppTest.from_file("streamlit_app.py", default_timeout=20)
        self.at.query_params["mode"] = "mobile"

    def tearDown(self) -> None:
        for path in [self.db_path, self.yaml_path]:
            if os.path.exists(path):
                os.remove(path)

    def _check_nav(self):
        html = "".join(m.body for m in self.at.markdown)
        self.assertIn("bottom-nav", html)

    def test_tabs_render_mobile(self) -> None:
        for tab in ["workouts", "library", "progress", "settings"]:
            self.at.query_params["tab"] = tab
            self.at.run()
            self._check_nav()

if __name__ == "__main__":
    unittest.main()
