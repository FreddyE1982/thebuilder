import os
import unittest
from fastapi.testclient import TestClient
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from rest_api import GymAPI

class RecentTemplatesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = 'test_recent.db'
        if os.path.exists(self.db):
            os.remove(self.db)
        self.api = GymAPI(db_path=self.db)
        self.client = TestClient(self.api.app)

    def tearDown(self) -> None:
        if os.path.exists(self.db):
            os.remove(self.db)

    def test_recent_templates(self) -> None:
        resp = self.client.post('/templates', params={'name': 'T1'})
        tid1 = resp.json()['id']
        self.client.post('/templates', params={'name': 'T2'})
        self.client.post(f'/templates/{tid1}/plan', params={'date': '2024-01-01'})
        resp = self.client.get('/templates/recent')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['id'], tid1)

if __name__ == '__main__':
    unittest.main()
