import os
import unittest
import sqlite3
import ml_service
import db

class MLServiceModelTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = 'test_ml.db'
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        # repositories
        self.repo = db.MLModelRepository(self.db_path)
        self.name_repo = db.ExerciseNameRepository(self.db_path)
        self.log_repo = db.MLLogRepository(self.db_path)
        self.status_repo = db.MLModelStatusRepository(self.db_path)
        self.name_repo.ensure(['Bench Press'])

    def tearDown(self) -> None:
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_performance_model_train_predict(self) -> None:
        svc = ml_service.PerformanceModelService(
            self.repo, self.name_repo, self.log_repo, self.status_repo, lr=0.1
        )
        svc.train('Bench Press', 5, 100.0, 8, 7)
        value, conf = svc.predict('Bench Press', 5, 100.0, 7)
        self.assertAlmostEqual(value, 1.2044939398765564)
        self.assertAlmostEqual(conf, 1.000880479812622)
        logs = self.log_repo.fetch('Bench Press')
        self.assertEqual(len(logs), 1)
        status = self.status_repo.fetch('performance_model')
        self.assertIsNotNone(status['last_train'])
        self.assertIsNotNone(status['last_predict'])

    def test_volume_model_train_predict(self) -> None:
        svc = ml_service.VolumeModelService(self.repo, lr=0.001, status_repo=self.status_repo)
        before = svc.predict([1.0, 2.0, 3.0], fallback=100.0)
        self.assertEqual(before, 100.0)
        svc.train([1.0, 2.0, 3.0], 150.0)
        after = svc.predict([1.0, 2.0, 3.0], fallback=100.0)
        self.assertAlmostEqual(after, -424.55363273620605)
        status = self.status_repo.fetch('volume_model')
        self.assertIsNotNone(status['last_train'])

    def test_readiness_model_train_predict(self) -> None:
        svc = ml_service.ReadinessModelService(self.repo, lr=0.01, status_repo=self.status_repo)
        before = svc.predict(1.0, 2.0, fallback=5.0)
        self.assertEqual(before, 5.0)
        svc.train(1.0, 2.0, 6.0)
        after = svc.predict(1.0, 2.0, fallback=5.0)
        self.assertAlmostEqual(after, 0.08296996355056763)
        status = self.status_repo.fetch('readiness_model')
        self.assertIsNotNone(status['last_train'])

if __name__ == '__main__':
    unittest.main()
