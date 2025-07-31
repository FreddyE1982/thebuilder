import os
import sys
import unittest
from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from rest_api import GymAPI

class PlanSearchTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = 'test_plan.db'
        self.yaml_path = 'test_plan.yaml'
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        if os.path.exists(self.yaml_path):
            os.remove(self.yaml_path)
        self.api = GymAPI(db_path=self.db_path, yaml_path=self.yaml_path)
        self.client = TestClient(self.api.app)
        self.client.post('/planned_workouts', params={'date':'2024-01-01','training_type':'strength'})
        self.client.post('/planned_workouts', params={'date':'2024-01-02','training_type':'cardio'})

    def tearDown(self) -> None:
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        if os.path.exists(self.yaml_path):
            os.remove(self.yaml_path)

    def test_search_by_training_type(self) -> None:
        resp = self.client.get('/planned_workouts/search', params={'training_type':'cardio'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['training_type'], 'cardio')

