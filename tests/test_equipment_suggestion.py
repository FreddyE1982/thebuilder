import os
import sys
import unittest
from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from rest_api import GymAPI

class EquipmentSuggestionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = 'test_suggest.db'
        self.yaml_path = 'test_suggest.yaml'
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        if os.path.exists(self.yaml_path):
            os.remove(self.yaml_path)
        self.api = GymAPI(db_path=self.db_path, yaml_path=self.yaml_path)
        self.client = TestClient(self.api.app)
        self.client.post('/equipment/types', params={'name': 'bar'})
        self.client.post('/equipment', params={'equipment_type':'bar','name':'A','muscles':'chest'})
        self.client.post('/equipment', params={'equipment_type':'bar','name':'B','muscles':'chest'})

    def tearDown(self) -> None:
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        if os.path.exists(self.yaml_path):
            os.remove(self.yaml_path)

    def test_suggest_endpoint(self) -> None:
        resp = self.client.get('/equipment/suggest', params={'exercise':'Bench Press'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn(resp.json()['equipment'], ['A','B'])

