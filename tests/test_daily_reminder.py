import os
import sys
import unittest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from rest_api import GymAPI

class DailyReminderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = "test_reminder.db"
        if os.path.exists(self.db):
            os.remove(self.db)
        self.api = GymAPI(db_path=self.db, start_scheduler=False, start_reminder=False)

    def tearDown(self) -> None:
        if os.path.exists(self.db):
            os.remove(self.db)

    def test_daily_reminder_adds_notification(self) -> None:
        self.api.settings.set_bool("daily_reminders_enabled", True)
        self.api.send_daily_reminder()
        self.assertEqual(self.api.notifications.unread_count(), 1)

if __name__ == "__main__":
    unittest.main()
