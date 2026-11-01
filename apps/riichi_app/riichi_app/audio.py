"""Robot microphone, Scribe, and cached ElevenLabs speech."""
import base64
import hashlib
import json
import threading
import time
from pathlib import Path
from .secrets import api_key

CACHE = Path.home() / ".cache" / "riichi" / "speech"

class Speaker:
    def __init__(self, robot, config, errors, before_say=None):
        self.robot, self.config, self.errors = robot, config, errors
        self.before_say = before_say
        self.lock = threading.Lock()
        self.busy = threading.Event()
        self.last_done = 0.0
        self.stop = threading.Event()
        self.threads = set()

    def say(self, line, done=None):
        if self.stop.is_set():
            return
        if self.before_say:
            self.before_say()
        self.busy.set()
        # voice_ids가 있으면 대사마다 목소리를 돌려 가며 쓴다
        voices = self.config.get("voice_ids") or [self.config["voice_id"]]
        self.turn = getattr(self, "turn", -1) + 1
        voice = voices[self.turn % len(voices)]
        def work():
            try:
                with self.lock:
                    digest = hashlib.sha256((voice + line).encode()).hexdigest()
                    file = CACHE / (digest + ".mp3")
                    if not file.is_file() or not file.stat().st_size:
                        from elevenlabs.client import ElevenLabs
                        CACHE.mkdir(parents=True, exist_ok=True)
                        tmp = file.with_suffix(".tmp")
                        with tmp.open("wb") as out:
                            for chunk in ElevenLabs(api_key=api_key()).text_to_speech.convert(
                                text=line, voice_id=voice,
                                model_id="eleven_multilingual_v2", output_format="mp3_44100_128"):
                                out.write(chunk)
                        if not tmp.stat().st_size:
                            raise RuntimeError("TTS가 빈 음성을 반환했습니다")
                        tmp.replace(file)
                    started = time.monotonic()
                    self.robot.media.play_sound(str(file.resolve()))
                    # Some media backends enqueue playback and return immediately.
                    try:
                        import miniaudio
                        info = miniaudio.get_file_info(str(file))
                        duration = info.duration
                    except Exception:
                        duration = max(1, len(line.split()) / 2.5)
                    self.stop.wait(max(0, min(30, duration + 0.2) - (time.monotonic() - started)))
            except Exception as exc:
                self.errors.put("음성 재생: " + str(exc))
            finally:
                self.last_done = time.monotonic()
                self.busy.clear()
                if done:
                    done()
                self.threads.discard(threading.current_thread())
        worker = threading.Thread(target=work, daemon=True)
        self.threads.add(worker)
        worker.start()

    def close(self):
        self.stop.set()
        for worker in list(self.threads):
            worker.join(timeout=3)

class ScribeListener:
    def __init__(self, robot, events, language):
        self.robot, self.events, self.language = robot, events, language
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def start(self):
        self.thread.start()

    def close(self):
        self.stop.set()
        def stop_recording():
            try:
                self.robot.media.stop_recording()
            except Exception:
                pass

        # A blocked media call must not hold the app's shutdown path.
        threading.Thread(target=stop_recording, daemon=True).start()
        self.thread.join(timeout=3)

    def run(self):
        from websockets.sync.client import connect
        import numpy as np
        recorded = False
        last_text, last_at = "", 0.0
        pending = None
        try:
            if self.robot.media.get_input_audio_samplerate() != 16000:
                raise RuntimeError("로봇 마이크는 16 kHz여야 합니다")
            self.robot.media.start_recording()
            recorded = True
            url = "wss://api.elevenlabs.io/v1/speech-to-text/realtime?model_id=scribe_v2_realtime&audio_format=pcm_16000&commit_strategy=vad&include_language_detection=true"
            if self.language in ("ko", "en"):
                url += "&language_code=" + self.language
            with connect(url, additional_headers={"xi-api-key": api_key()}, open_timeout=10, close_timeout=2) as ws:
                def send():
                    try:
                        while not self.stop.is_set():
                            sample = self.robot.media.get_audio_sample()
                            if sample is None:
                                self.stop.wait(0.01)
                                continue
                            mono = sample.mean(axis=1) if sample.ndim == 2 else sample
                            raw = (np.clip(mono, -1, 1)*32767).astype("<i2").tobytes()
                            ws.send(json.dumps({"message_type": "input_audio_chunk",
                                                "audio_base_64": base64.b64encode(raw).decode()}))
                    except Exception as exc:
                        if not self.stop.is_set():
                            self.events.put(("error", "STT 전송: " + str(exc)))
                sender = threading.Thread(target=send, daemon=True)
                sender.start()
                try:
                    while not self.stop.is_set():
                        try:
                            data = json.loads(ws.recv(timeout=0.5))
                        except TimeoutError:
                            if pending and time.monotonic() - pending[1] >= 0.5:
                                spoken = pending[0]
                                if spoken != last_text or time.monotonic() - last_at > 2:
                                    self.events.put(("transcript", {"text": spoken, "language_code": None}))
                                    last_text, last_at = spoken, time.monotonic()
                                pending = None
                            continue
                        if data.get("message_type") == "committed_transcript" and data.get("text"):
                            pending = (data["text"], time.monotonic())
                        elif data.get("message_type") == "committed_transcript_with_timestamps" and data.get("text"):
                            spoken = data["text"]
                            if spoken != last_text or time.monotonic() - last_at > 2:
                                self.events.put(("transcript", {"text": spoken, "language_code": data.get("language_code")}))
                                last_text, last_at = spoken, time.monotonic()
                            pending = None
                        elif data.get("message_type") in ("error", "rate_limited"):
                            self.events.put(("error", "STT: " + str(data.get("message") or data.get("error"))))
                            break
                finally:
                    self.stop.set()
                    sender.join(timeout=3)
        except Exception as exc:
            if not self.stop.is_set():
                self.events.put(("error", "STT 연결: " + str(exc)))
        finally:
            self.stop.set()
            if recorded:
                try:
                    self.robot.media.stop_recording()
                except Exception:
                    pass
