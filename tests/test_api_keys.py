import os
import unittest
from fastapi.testclient import TestClient
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from rest_api import GymAPI

class APIKeyTestCase(unittest.TestCase):
    def setUp(self):
        self.db = "test_keys.db"
        self.yaml = "test_keys.yaml"
        if os.path.exists(self.db):
            os.remove(self.db)
        if os.path.exists(self.yaml):
            os.remove(self.yaml)
        self.api = GymAPI(db_path=self.db, yaml_path=self.yaml)
        self.client = TestClient(self.api.app)

    def tearDown(self):
        if os.path.exists(self.db):
            os.remove(self.db)
        if os.path.exists(self.yaml):
            os.remove(self.yaml)

    def test_api_key_crud(self):
        resp = self.client.post("/api_keys", params={"name": "service", "key": "abc"})
        self.assertEqual(resp.status_code, 200)
        kid = resp.json()["id"]

        resp = self.client.get("/api_keys")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [{"id": kid, "name": "service", "key": "abc"}])

        resp = self.client.delete(f"/api_keys/{kid}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "deleted"})
        self.assertEqual(self.client.get("/api_keys").json(), [])

if __name__ == "__main__":
    unittest.main()
