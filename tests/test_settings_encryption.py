import os
import sys
import unittest
import keyring
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import YamlConfig

class DummyKeyring(keyring.backend.KeyringBackend):
    priority = 1
    def __init__(self):
        self.store = {}
    def get_password(self, service, username):
        return self.store.get((service, username))
    def set_password(self, service, username, password):
        self.store[(service, username)] = password
    def delete_password(self, service, username):
        self.store.pop((service, username), None)

class SettingsEncryptionTest(unittest.TestCase):
    def setUp(self) -> None:
        keyring.set_keyring(DummyKeyring())
        os.environ['ENCRYPT_SETTINGS'] = '1'
        self.path = 'enc_settings.yaml'
        if os.path.exists(self.path):
            os.remove(self.path)

    def tearDown(self) -> None:
        if os.path.exists(self.path):
            os.remove(self.path)
        os.environ.pop('ENCRYPT_SETTINGS', None)

    def test_encrypt_and_load(self) -> None:
        cfg = YamlConfig(self.path)
        cfg.save({'slack_webhook_url':'secret', 'theme':'light'})
        self.assertTrue(os.path.exists(self.path))
        data = cfg.load()
        self.assertEqual(data['slack_webhook_url'], 'secret')
        self.assertEqual(data['theme'], 'light')

