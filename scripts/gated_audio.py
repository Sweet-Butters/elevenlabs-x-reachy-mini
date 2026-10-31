"""Play a complete agent text answer in the configured Sena voice."""
import threading
import time
import re
from pathlib import Path

from common import api_key


class ReplySpeaker:
    def __init__(self, robot=None, scratch=None, other_audio=None):
        self.robot = robot
        self.scratch = Path(scratch)
        self.other_audio = other_audio
        self.busy = threading.Event()
        self.thread = None
        self.lock = threading.Lock()
        self.pending = 0
        self.play_lock = threading.Lock()

    def begin_turn(self):
        with self.lock:
            self.pending += 1
            self.busy.set()

    def speak_text(self, answer, on_done=None):
        def work():
            with self.play_lock:
              try:
                from elevenlabs.client import ElevenLabs
                import miniaudio
                self.scratch.mkdir(parents=True, exist_ok=True)
                file = self.scratch / "riichi-agent-reply.mp3"
                client = ElevenLabs(api_key=api_key())
                spoken = re.sub(r"\[[^]]{1,30}\]", "", answer).strip()
                audio = client.text_to_speech.convert(
                    text=spoken, voice_id="vJ170fCwESgE1tjW39So",
                    model_id="eleven_multilingual_v2", output_format="mp3_44100_128")
                with file.open("wb") as out:
                    for chunk in audio:
                        out.write(chunk)
                if not file.stat().st_size:
                    raise RuntimeError("빈 음성")
                decoded = miniaudio.decode_file(str(file), nchannels=1, sample_rate=44100)
                duration = len(decoded.samples) / 2 / 44100
                while self.other_audio is not None and self.other_audio.is_set():
                    time.sleep(0.05)
                print(f"에이전트 음성 재생: {duration:.1f}초 ({'로봇' if self.robot else '노트북'})", flush=True)
                if self.robot:
                    self.robot.media.play_sound(str(file.resolve()))
                    time.sleep(duration + 0.2)
                else:
                    from play_lines import play
                    play(file)
              except Exception as exc:
                print(f"에이전트 음성 재생 실패: {exc}", flush=True)
              finally:
                with self.lock:
                    self.pending = max(0, self.pending - 1)
                    if not self.pending:
                        self.busy.clear()
                if on_done:
                    on_done()
        self.thread = threading.Thread(target=work, daemon=True)
        self.thread.start()

    def wait(self):
        if self.thread:
            self.thread.join(timeout=15)
