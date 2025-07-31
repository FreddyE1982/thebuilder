import unittest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from client import BuilderClient
from rest_api import GymAPI

class ClientTest(unittest.TestCase):
    def setUp(self) -> None:
        self.api = GymAPI(db_path='workout.db')
        self.client = BuilderClient(base_url='http://testserver')
        self.client.api = self.api  # monkeypatch requests? we'll not do network

    def test_create_workout(self) -> None:
        wid = self.client.api.workouts.create('2020-01-01')
        self.assertIsInstance(wid, int)

if __name__ == '__main__':
    unittest.main()

