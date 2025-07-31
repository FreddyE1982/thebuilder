import os
import yaml
import keyring

APP_VERSION = "1.0.0"


class YamlConfig:
    """Load and save settings to a YAML file with optional encryption."""

    SENSITIVE_KEYS = {
        "slack_webhook_url",
        "webhook_url",
    }

    def __init__(self, path: str = "settings.yaml") -> None:
        self.path = path
        self.encrypt = os.environ.get("ENCRYPT_SETTINGS") == "1"
        self.service = "thebuilder"

    def load(self) -> dict:
        if not os.path.exists(self.path):
            return {}
        with open(self.path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if self.encrypt:
            for key in list(data.keys()):
                if key in self.SENSITIVE_KEYS:
                    secret = keyring.get_password(self.service, key)
                    if secret is not None:
                        data[key] = secret
                    else:
                        data.pop(key, None)
        return data

    def save(self, data: dict) -> None:
        out = dict(data)
        if self.encrypt:
            for key in self.SENSITIVE_KEYS:
                if key in out:
                    keyring.set_password(self.service, key, str(out[key]))
                    out[key] = True
        with open(self.path, "w", encoding="utf-8") as f:
            yaml.safe_dump(out, f)
