import os
import yaml

APP_VERSION = "1.0.0"


class YamlConfig:
    """Load and save settings to a YAML file."""

    def __init__(self, path: str = "settings.yaml") -> None:
        self.path = path

    def load(self) -> dict:
        if not os.path.exists(self.path):
            return {}
        with open(self.path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data or {}

    def save(self, data: dict) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f)
