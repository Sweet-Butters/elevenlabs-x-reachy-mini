"""Motion scheduling contract without a robot or network."""

import queue
import threading
import time
import unittest
from unittest.mock import patch

from riichi_app.emotion_motion import DANCES_DATASET, EMOTIONS_DATASET, IDLE_EMOTIONS, EmotionMotion


class FakeMoves:
    def __init__(self, dataset):
        self.moves = ({name: name for name in IDLE_EMOTIONS} if dataset == EMOTIONS_DATASET else
                      {name: name for name in ("groovy_sway_and_roll", "side_peekaboo",
                                               "yeah_nod", "uh_huh_tilt", "pendulum_swing")})

    def list_moves(self):
        return list(self.moves)

    def get(self, name):
        return name


class FakeRobot:
    def __init__(self, block=False):
        self.played = []
        self.entered = threading.Event()
        self.release = threading.Event()
        self.block = block

    def play_move(self, move, **kwargs):
        self.played.append((move, kwargs))
        self.entered.set()
        if self.block:
            self.release.wait(5)

    def cancel_move(self):
        self.release.set()


class MotionTests(unittest.TestCase):
    def test_idle_varies_and_alternates(self):
        robot = FakeRobot()
        with patch("riichi_app.emotion_motion.RecordedMoves", FakeMoves):
            motion = EmotionMotion(robot, queue.Queue())
            motion._load()
            for _ in range(8):
                motion.next_at = 0
                motion.tick()
                motion.worker.join(0.5)
        names = [name for name, _ in robot.played]
        self.assertEqual(len(names), 8)
        self.assertTrue(all(name in IDLE_EMOTIONS for name in names[::2]))
        self.assertTrue(all(name in FakeMoves(DANCES_DATASET).moves for name in names[1::2]))
        self.assertTrue(all(name not in names[max(0, i - 4):i] for i, name in enumerate(names)))
        self.assertTrue(all(kwargs == {"initial_goto_duration": 0.4, "sound": False}
                            for _, kwargs in robot.played))
        motion.close()

    def test_speech_pauses_and_cancels_motion(self):
        robot = FakeRobot(block=True)
        motion = EmotionMotion(robot, queue.Queue())
        motion.libraries = {"emotion": FakeMoves(EMOTIONS_DATASET)}
        motion.tick()
        self.assertTrue(robot.entered.wait(0.5))
        motion.pause()  # Called before speaker.busy is set.
        motion.worker.join(0.5)
        self.assertFalse(motion.worker.is_alive())
        count = len(robot.played)
        motion.tick(enabled=False)
        self.assertEqual(len(robot.played), count)
        motion.close()

    def test_stop_does_not_wait_for_stalled_sdk(self):
        robot = FakeRobot(block=True)
        robot.cancel_move = lambda: None  # Simulate a stalled SDK playback.
        motion = EmotionMotion(robot, queue.Queue())
        motion.libraries = {"emotion": FakeMoves(EMOTIONS_DATASET)}
        motion.tick()
        self.assertTrue(robot.entered.wait(0.5))
        started = time.monotonic()
        motion.close()
        self.assertLess(time.monotonic() - started, 0.3)
        robot.release.set()

    def test_app_stop_has_one_cleanup_deadline(self):
        from riichi_app.main import RiichiApp

        app = object.__new__(RiichiApp)
        app.errors = queue.Queue()
        app.config = {}
        app.listener = type("Listener", (), {"close": lambda self: time.sleep(5)})()
        app.session = object()
        app.speaker = None
        stop = threading.Event()
        stop.set()
        with (patch("riichi_app.main.EmotionMotion") as motion_class,
              patch("riichi_app.main.Speaker") as speaker_class,
              patch.object(RiichiApp, "_event"),
              patch.object(RiichiApp, "_init_vision"),
              patch.object(RiichiApp, "_switch"),
              patch.object(RiichiApp, "_close_session", side_effect=lambda session: time.sleep(5))):
            speaker_class.return_value.close.side_effect = lambda: time.sleep(5)
            started = time.monotonic()
            app.run(FakeRobot(), stop)
            self.assertLess(time.monotonic() - started, 3.5)
            motion_class.return_value.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
