import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import riichi
from timer_audio import clip


class FakeMedia:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def play_sound(self, filename):
        self.calls.append(filename)
        if self.fail:
            raise RuntimeError("speaker unavailable")


class TimerRobotAudioTest(unittest.TestCase):
    def test_speak_routes_each_announcement(self):
        cases = (("start", 180), ("left", 120), ("left", 60), ("left", 30), ("up", 0))
        if os.environ.get("TIMER_AUDIO_DIR"):
            audio = Path(os.environ["TIMER_AUDIO_DIR"])
        else:
            temporary = tempfile.TemporaryDirectory()
            self.addCleanup(temporary.cleanup)
            audio = Path(temporary.name)
            (audio / "timer" / "ko").mkdir(parents=True)
            for kind, seconds in cases:
                (audio / "timer" / "ko" / (clip(kind, seconds) + ".mp3")).write_bytes(b"clip")
        controller = riichi.Controller(SimpleNamespace(seconds=180, minutes=3, offline=True))
        with patch.object(riichi, "path", side_effect=lambda kind, seconds, lang:
                          audio / "timer" / lang / (clip(kind, seconds) + ".mp3")), \
             patch("play_lines.play") as laptop, patch("builtins.print") as output:
            for kind, seconds in cases:
                filename = audio / "timer" / "ko" / (clip(kind, seconds) + ".mp3")
                self.assertTrue(filename.is_file(), filename)
                with self.subTest(kind=kind, seconds=seconds, route="robot"):
                    media = FakeMedia()
                    controller.robot = SimpleNamespace(media=media)
                    controller.speak(kind, seconds, "ko")
                    self.assertEqual(media.calls, [str(filename.resolve())])
                    laptop.assert_not_called()
                with self.subTest(kind=kind, seconds=seconds, route="laptop"):
                    controller.robot = None
                    controller.speak(kind, seconds, "ko")
                    laptop.assert_called_once_with(filename)
                    laptop.reset_mock()
                with self.subTest(kind=kind, seconds=seconds, route="fallback"):
                    media = FakeMedia(fail=True)
                    controller.robot = SimpleNamespace(media=media)
                    output.reset_mock()
                    controller.speak(kind, seconds, "ko")
                    self.assertEqual(media.calls, [str(filename.resolve())])
                    laptop.assert_called_once_with(filename)
                    self.assertEqual(output.call_count, 1)
                    self.assertIn("speaker unavailable", output.call_args.args[0])
                    laptop.reset_mock()


if __name__ == "__main__":
    unittest.main()
