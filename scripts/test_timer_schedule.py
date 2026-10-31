import unittest

from pitch_timer import announcement_schedule


class TimerScheduleTest(unittest.TestCase):
    def test_three_minutes(self):
        self.assertEqual(announcement_schedule(180), [120, 60, 30, 0])

    def test_ten_minutes(self):
        self.assertEqual(announcement_schedule(600), [300, 60, 30, 0])

    def test_two_to_four(self):
        self.assertEqual(announcement_schedule(240), [180, 120, 60, 30, 0])

    def test_short(self):
        self.assertEqual(announcement_schedule(60), [30, 10, 0])
        self.assertEqual(announcement_schedule(30), [10, 0])
        self.assertEqual(announcement_schedule(8), [0])

    def test_uneven(self):
        self.assertEqual(announcement_schedule(330), [120, 60, 30, 0])
        self.assertEqual(announcement_schedule(90), [60, 30, 0])


if __name__ == "__main__":
    unittest.main()
