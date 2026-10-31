"""Cached, interruptible recorded motion for Riichi's quiet moments."""

from collections import deque
import random
import threading
import time

from reachy_mini.motion.recorded_move import RecordedMoves


EMOTIONS_DATASET = "pollen-robotics/reachy-mini-emotions-library"
DANCES_DATASET = "pollen-robotics/reachy-mini-dances-library"

# Names are taken from the official emotions dataset. Keep idle welcoming and upbeat.
IDLE_EMOTIONS = (
    "cheerful1", "curious1", "welcoming1", "welcoming2", "helpful1",
    "enthusiastic2", "grateful1", "loving1", "inquiring2", "proud2",
)


class EmotionMotion:
    def __init__(self, robot, errors, rng=None):
        self.robot, self.errors = robot, errors
        self.rng = rng or random.Random()
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.libraries = {}
        self.recent = deque(maxlen=4)
        self.next_kind = "emotion"
        self.next_at = 0.0
        self.worker = None

    def start(self):
        # RecordedMoves uses the HF cache first; its first network download can be slow.
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        for kind, dataset in (("emotion", EMOTIONS_DATASET), ("dance", DANCES_DATASET)):
            if self.stop_event.is_set():
                return
            try:
                library = RecordedMoves(dataset)
                with self.lock:
                    self.libraries[kind] = library
            except Exception as exc:
                self.errors.put(f"{kind} 동작 로드: {exc}")

    def tick(self, enabled=True):
        if not enabled or self.stop_event.is_set():
            return
        with self.lock:
            if (self.worker is not None and self.worker.is_alive()) or time.monotonic() < self.next_at:
                return
            available = {}
            for kind, library in self.libraries.items():
                names = (IDLE_EMOTIONS if kind == "emotion" else
                         tuple(name for name in library.list_moves() if name != "stumble_and_recover"))
                available[kind] = [(kind, name) for name in names if name in library.moves]
            kind = self.next_kind if available.get(self.next_kind) else (
                "emotion" if available.get("emotion") else "dance")
            choices = available.get(kind, [])
            if not choices:
                return
            fresh = [choice for choice in choices if choice not in self.recent]
            choice = self.rng.choice(fresh or choices)
            self.recent.append(choice)
            self.next_kind = "dance" if kind == "emotion" else "emotion"
            library = self.libraries[kind]
            self.worker = threading.Thread(target=self._play, args=(library, choice[1]), daemon=True)
            self.worker.start()

    def _play(self, library, name):
        try:
            if not self.stop_event.is_set():
                self.robot.play_move(library.get(name), initial_goto_duration=0.4, sound=False)
        except Exception as exc:
            self.errors.put(f"녹화 동작 {name}: {exc}")
        finally:
            with self.lock:
                self.next_at = time.monotonic() + self.rng.uniform(1.0, 2.5)

    def pause(self):
        # Call before TTS starts: SDK cancel_move also stops its media playback.
        with self.lock:
            playing = self.worker is not None and self.worker.is_alive()
            self.next_at = max(self.next_at, time.monotonic() + 0.6)
        if playing:
            try:
                self.robot.cancel_move()
            except Exception as exc:
                self.errors.put(f"동작 중단: {exc}")

    def close(self):
        self.stop_event.set()
        self.pause()
        # Never join the worker or HF loader: a stalled SDK call must not block stop.
