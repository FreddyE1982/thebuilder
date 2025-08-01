import os
import os
import sys
import shutil
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ml_plugins import PluginManager, MLModelPlugin


class DummyService:
    pass


class TestPluginManager(unittest.TestCase):
    def test_loads_plugins(self):
        tmp_dir = "tmp_plugins"
        os.makedirs(tmp_dir, exist_ok=True)
        with open(os.path.join(tmp_dir, "__init__.py"), "w", encoding="utf-8") as f:
            f.write("")
        with open(os.path.join(tmp_dir, "plugin.py"), "w", encoding="utf-8") as f:
            f.write(
                "from ml_plugins import MLModelPlugin\n"
                "class P(MLModelPlugin):\n"
                "    def register(self, service):\n"
                "        service.flag = True\n"
            )
        manager = PluginManager(tmp_dir)
        svc = DummyService()
        manager.load_plugins(svc)
        self.assertTrue(getattr(svc, "flag", False))
        # cleanup
        shutil.rmtree(tmp_dir)


if __name__ == "__main__":
    unittest.main()

