"""One laptop-first Reachy controller: conversation, silent timer and welcome."""
import argparse
import base64
import json
import queue
import re
import sys
import threading
import time

from common import AGENT_ID, api_key
from pitch_timer import announcement_schedule, clock_text
from timer_audio import path, phrase


def duration_from_text(text):
    s = text.lower().replace("타이머 모드", "타이머")
    if not re.search(r"타이머|timer", s):
        return None
    minutes = re.search(r"(\d+)\s*(?:분|minutes?|mins?)", s)
    seconds = re.search(r"(\d+)\s*(?:초|seconds?|secs?)", s)
    value = (int(minutes.group(1)) * 60 if minutes else 0) + (int(seconds.group(1)) if seconds else 0)
    return value if 0 < value <= 3600 else None


def passive_command(text, mode):
    s = re.sub(r"[^\w]", "", text.lower())
    if mode == "timer":
        if s in ("타이머모드해제", "타이머모드꺼", "타이머모드off", "timermodeoff"):
            return ("conversation", None)
        length = duration_from_text(text)
        return ("length", length) if length else None
    if mode == "welcome" and s in ("웰컴모드종료", "welcomemodeoff"):
        return ("conversation", None)
    return None


class ScribeListener:
    """Only committed Scribe transcripts enter the controller; no audio is stored."""
    def __init__(self, events):
        self.events = events
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def start(self):
        self.thread.start()

    def close(self):
        self.stop.set()
        self.thread.join(timeout=3)

    def run(self):
        import pyaudio
        from websockets.sync.client import connect
        audio = pyaudio.PyAudio()
        stream = None
        try:
            stream = audio.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True,
                                frames_per_buffer=1600)
            url = "wss://api.elevenlabs.io/v1/speech-to-text/realtime?model_id=scribe_v2_realtime&audio_format=pcm_16000&commit_strategy=vad"
            with connect(url, additional_headers={"xi-api-key": api_key()}, open_timeout=10, close_timeout=2) as ws:
                def send():
                    try:
                        while not self.stop.is_set():
                            raw = stream.read(1600, exception_on_overflow=False)
                            ws.send(json.dumps({"message_type": "input_audio_chunk", "audio_base_64": base64.b64encode(raw).decode()}))
                    except Exception as exc:
                        if not self.stop.is_set():
                            self.events.put(("error", f"STT 전송: {exc}"))
                sender = threading.Thread(target=send, daemon=True)
                sender.start()
                while not self.stop.is_set():
                    try:
                        data = json.loads(ws.recv(timeout=0.5))
                    except TimeoutError:
                        continue
                    if data.get("message_type") == "session_started":
                        self.events.put(("stt_ready", None))
                    elif data.get("message_type") == "committed_transcript" and data.get("text"):
                        self.events.put(("transcript", data["text"]))
                    elif data.get("message_type") in ("error", "rate_limited"):
                        self.events.put(("error", str(data.get("message") or data.get("error") or data)))
                        break
        except Exception as exc:
            self.events.put(("error", f"STT 연결: {exc}"))
        finally:
            self.stop.set()
            if stream:
                stream.stop_stream()
                stream.close()
            audio.terminate()


class Controller:
    def __init__(self, args):
        self.args = args
        self.mode = None
        self.length = args.seconds if args.seconds is not None else round(args.minutes * 60)
        self.current_length = self.length
        self.events = queue.Queue()
        self.session = None
        self.listener = None
        self.welcome_stop = None
        self.welcome_thread = None
        self.gaze_stop = None
        self.gaze_thread = None
        self.state = "ready"
        self.number = 1
        self.lang = "ko"
        self.active_lang = "ko"
        self.elapsed = 0.0
        self.resumed_at = 0.0
        self.fired = set()
        self.last_display = ""
        self.voice_id = None
        self.session_epoch = 0

    def speak(self, kind, seconds=0, lang=None):
        from play_lines import play
        lang = lang or self.active_lang
        file = path(kind, seconds, lang)
        if file.is_file() and file.stat().st_size:
            try:
                play(file)
                return
            except Exception as exc:
                print(f"재생 실패: {exc}", flush=True)
        line = phrase(kind, seconds, lang)
        print(f"MP3 없음: {line}", flush=True)
        if self.args.offline:
            return
        try:
            from elevenlabs.client import ElevenLabs
            if not self.voice_id:
                client = ElevenLabs(api_key=api_key())
                self.voice_id = client.conversational_ai.agents.get(AGENT_ID).conversation_config.tts.voice_id
            else:
                client = ElevenLabs(api_key=api_key())
            # Runtime fallback is decoded in memory; no audio file is written.
            import miniaudio
            import pyaudio
            data = b"".join(client.text_to_speech.convert(text=line, voice_id=self.voice_id,
                        model_id="eleven_multilingual_v2", output_format="mp3_44100_128"))
            decoded = miniaudio.decode(data, nchannels=2, sample_rate=44100)
            audio = pyaudio.PyAudio()
            try:
                output = audio.open(format=pyaudio.paInt16, channels=2, rate=44100, output=True)
                try:
                    output.write(decoded.samples)
                finally:
                    output.close()
            finally:
                audio.terminate()
        except Exception as exc:
            print(f"실시간 TTS 불가: {exc}", flush=True)

    def keyboard(self):
        if self.args.text:
            while True:
                try:
                    line = input().strip()
                except EOFError:
                    self.events.put(("quit", None))
                    return
                if line.lower() in ("/quit", "/exit"):
                    self.events.put(("quit", None))
                    return
                self.events.put(("text", line))
        else:
            import msvcrt
            while True:
                key = msvcrt.getwch()
                if key in ("\x00", "\xe0"):
                    code = msvcrt.getwch()
                    if code in (";", "<", "="):
                        self.events.put(("switch", {";": "conversation", "<": "timer", "=": "welcome"}[code]))
                else:
                    if key.lower() == "n":
                        print("새 길이 (예: 5분, 30초): ", end="", flush=True)
                        chars = []
                        while True:
                            part = msvcrt.getwch()
                            if part == "\r":
                                print(flush=True)
                                self.events.put(("length", "".join(chars)))
                                break
                            if part == "\b" and chars:
                                chars.pop()
                                print("\b \b", end="", flush=True)
                            elif part.isprintable():
                                chars.append(part)
                                print(part, end="", flush=True)
                    else:
                        self.events.put(("key", key.lower()))

    def connect(self):
        from elevenlabs.client import ElevenLabs
        from elevenlabs.conversational_ai.conversation import Conversation, ClientTools, ConversationInitiationData
        tools = ClientTools()
        def set_mode(parameters):
            target = parameters.get("mode")
            length = parameters.get("duration_seconds")
            print(f"도구 set_mode: {target}, duration_seconds={length}", flush=True)
            self.events.put(("tool", (target, length)))
            return "Switching mode now."
        tools.register("set_mode", set_mode)
        self.session_epoch += 1
        epoch = self.session_epoch
        config = ConversationInitiationData(conversation_config_override={"conversation": {"text_only": True}}) if self.args.text else None
        kwargs = {}
        if not self.args.text:
            from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
            kwargs["audio_interface"] = DefaultAudioInterface()
        self.session = Conversation(ElevenLabs(api_key=api_key()), AGENT_ID, requires_auth=True,
            client_tools=tools, config=config,
            callback_agent_response=lambda answer: self.events.put(("answer", (epoch, answer))),
            callback_user_transcript=lambda transcript: print(f"나> {transcript}", flush=True), **kwargs)
        self.session.start_session()
        print("에이전트 연결 중...", flush=True)

    def disconnect(self):
        if self.session:
            session, self.session = self.session, None
            session.end_session()
            session.wait_for_session_end()
            print("에이전트 연결 종료", flush=True)

    def switch(self, target):
        if target == self.mode:
            return
        if self.mode == "conversation":
            self.disconnect()
        if self.gaze_stop:
            self.gaze_stop.set()
            self.gaze_thread.join(timeout=5)
            self.gaze_stop = self.gaze_thread = None
        if self.listener:
            self.listener.close()
            self.listener = None
        if self.welcome_stop:
            self.welcome_stop.set()
            self.welcome_thread.join(timeout=5)
            self.welcome_stop = self.welcome_thread = None
        self.mode = target
        print(f"\n========== 리치 모드: {target.upper()} ==========" , flush=True)
        print("F1 대화 · F2 타이머 · F3 환영 | 타이머: Enter 시작, p 정지, r 초기화, k/e 언어, n 길이, q 종료", flush=True)
        if target == "conversation":
            if self.args.robot and not self.args.no_track:
                self.gaze_stop = threading.Event()
                self.gaze_thread = threading.Thread(target=self.run_gaze, daemon=True)
                self.gaze_thread.start()
            elif self.args.robot:
                from person_gaze import neutral
                from reachy_mini import ReachyMini
                from robot_host import resolve_robot_host
                host, _ = resolve_robot_host(self.args.host)
                with ReachyMini(host=host, connection_mode="network", media_backend="default", timeout=15) as robot:
                    neutral(robot)
            self.connect()
        else:
            if target == "timer" and self.args.robot:
                from person_gaze import neutral
                from reachy_mini import ReachyMini
                from robot_host import resolve_robot_host
                host, _ = resolve_robot_host(self.args.host)
                with ReachyMini(host=host, connection_mode="network", media_backend="default", timeout=15) as robot:
                    neutral(robot)
            if not self.args.text:
                self.listener = ScribeListener(self.events)
                self.listener.start()
            if target == "timer":
                self.state = "ready"
                self.show_timer(True)
            else:
                import welcome_mode
                self.welcome_stop = threading.Event()
                welcome_args = ["--camera", self.args.camera, "--detector", self.args.detector]
                if self.args.robot:
                    welcome_args.append("--robot")
                if self.args.no_track:
                    welcome_args.append("--no-track")
                if self.args.host:
                    welcome_args.extend(("--host", self.args.host))
                if self.args.preview:
                    welcome_args.append("--preview")
                self.welcome_thread = threading.Thread(target=self.run_welcome, args=(welcome_mode, welcome_args), daemon=True)
                self.welcome_thread.start()

    def run_gaze(self):
        try:
            import cv2
            from reachy_mini import ReachyMini
            from person_gaze import PersonGaze
            from robot_host import resolve_robot_host
            from welcome_mode import PersonDetector
            host, _ = resolve_robot_host(self.args.host)
            with ReachyMini(host=host, connection_mode="network", media_backend="default", timeout=15) as robot:
                detector = PersonDetector(cv2)
                gaze = PersonGaze(robot, log=True)
                print("대화 모드 사람 추적 시작", flush=True)
                while not self.gaze_stop.is_set():
                    start = time.monotonic()
                    frame = robot.media.get_frame()
                    if frame is not None:
                        height, width = frame.shape[:2]
                        gaze.update(detector.detect(frame), width, height)
                    self.gaze_stop.wait(max(0, 0.25 - (time.monotonic() - start)))
        except Exception as exc:
            self.events.put(("error", f"사람 추적: {exc}"))

    def run_welcome(self, module, argv):
        try:
            module.main(self.welcome_stop, argv)
        except Exception as exc:
            self.events.put(("error", f"환영 모드: {exc}"))

    def show_timer(self, force=False):
        if self.mode != "timer":
            return
        current = self.elapsed + (time.monotonic() - self.resumed_at) if self.state == "running" else self.elapsed
        active_length = self.length if self.state == "ready" else self.current_length
        display = f"발표 {self.number:02d} [{self.active_lang if self.state != 'ready' else self.lang}] {clock_text(active_length-current)} {self.state} | 다음 길이 {clock_text(self.length)}"
        if force or display != self.last_display:
            print(display, flush=True)
            self.last_display = display

    def tick(self):
        if self.mode != "timer" or self.state != "running":
            return
        remaining = self.current_length - (self.elapsed + time.monotonic() - self.resumed_at)
        for point in announcement_schedule(self.current_length):
            if remaining <= point and point not in self.fired:
                self.fired.add(point)
                if point == 0:
                    self.state = "done"
                    self.elapsed = self.current_length
                    print(f"발표 {self.number:02d} 종료", flush=True)
                threading.Thread(target=self.speak, args=(("up" if point == 0 else "left"), point, self.active_lang), daemon=True).start()
        self.show_timer()

    def timer_key(self, key):
        if key in ("\r", " "):
            if self.state in ("ready", "done"):
                if self.state == "done":
                    self.number += 1
                self.state, self.elapsed, self.fired = "running", 0.0, set()
                self.current_length = self.length
                self.active_lang = self.lang
                self.resumed_at = time.monotonic()
                print(f"발표 {self.number:02d} 시작", flush=True)
                threading.Thread(target=self.speak, args=("start", self.current_length, self.active_lang), daemon=True).start()
        elif key == "p" and self.state in ("running", "paused"):
            if self.state == "running":
                self.elapsed += time.monotonic() - self.resumed_at
                self.state = "paused"
            else:
                self.resumed_at = time.monotonic()
                self.state = "running"
        elif key == "r":
            self.state, self.elapsed, self.fired = "ready", 0.0, set()
        elif key in ("k", "e"):
            self.lang = "ko" if key == "k" else "en"
        self.show_timer(True)

    def set_length(self, value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            print("길이 인식 실패", flush=True)
            return
        if not 1 <= value <= 3600:
            print("길이는 1~3600초여야 합니다.", flush=True)
            return
        self.length = value
        print(f"다음 발표 길이: {clock_text(value)}", flush=True)
        self.show_timer(True)

    def handle(self, kind, value):
        if kind == "quit" or (kind == "key" and value == "q"):
            return False
        if kind == "error":
            print(value, flush=True)
        elif kind == "stt_ready":
            print("Scribe STT 연결됨", flush=True)
        elif kind == "answer":
            epoch, answer = value
            if self.mode == "conversation" and epoch == self.session_epoch:
                print(f"리치> {answer}", flush=True)
        elif kind == "switch":
            self.switch(value)
        elif kind == "tool":
            target, length = value
            if target in ("conversation", "timer", "welcome"):
                if length is not None:
                    self.set_length(length)
                # Let the SDK finish its client-tool callback before closing its socket.
                time.sleep(0.25)
                self.switch(target)
                if target == "timer" and length is not None:
                    self.timer_key("\r")
        elif kind == "length":
            self.set_length(duration_from_text("타이머 " + value))
        elif kind in ("transcript", "text"):
            if kind == "text" and value.lower() in ("/f1", "/f2", "/f3"):
                self.switch({"/f1": "conversation", "/f2": "timer", "/f3": "welcome"}[value.lower()])
                return True
            if kind == "text" and value.lower() in ("/enter", "/p", "/r", "/k", "/e") and self.mode == "timer":
                self.timer_key("\r" if value.lower() == "/enter" else value[-1].lower())
                return True
            print(f"인식> {value}" if self.mode != "conversation" else f"나> {value}", flush=True)
            if self.mode == "conversation":
                if kind == "text" and self.session:
                    deadline = time.monotonic() + 15
                    while self.session._ws is None and time.monotonic() < deadline:
                        time.sleep(0.05)
                    if self.session._ws:
                        self.session.send_user_message(value)
            else:
                command = passive_command(value, self.mode)
                if command:
                    target, length = command
                    if target == "length":
                        self.set_length(length)
                    else:
                        print("대화 모드로 돌아갈게요.", flush=True)
                        self.switch(target)
                else:
                    print("무시됨 (에이전트 연결 없음)", flush=True)
        elif kind == "key" and self.mode == "timer":
            self.timer_key(value)
        return True

    def run(self):
        threading.Thread(target=self.keyboard, daemon=True).start()
        started = time.monotonic()
        try:
            self.switch(self.args.mode)
            while True:
                if self.args.max_seconds and time.monotonic() - started >= self.args.max_seconds:
                    break
                self.tick()
                try:
                    kind, value = self.events.get(timeout=0.1)
                except queue.Empty:
                    continue
                if not self.handle(kind, value):
                    break
        finally:
            self.disconnect()
            if self.gaze_stop:
                self.gaze_stop.set()
                self.gaze_thread.join(timeout=5)
            if self.listener:
                self.listener.close()
            if self.welcome_stop:
                self.welcome_stop.set()
                self.welcome_thread.join(timeout=5)


def main():
    parser = argparse.ArgumentParser(description="리치 통합 모드 컨트롤러")
    parser.add_argument("--mode", choices=("conversation", "timer", "welcome"), default="conversation")
    parser.add_argument("--minutes", type=float, default=3)
    parser.add_argument("--seconds", type=int)
    parser.add_argument("--text", action="store_true", help="마이크 대신 터미널 문장으로 동작 검증")
    parser.add_argument("--offline", action="store_true", help="클립 누락 시 TTS 건너뜀")
    parser.add_argument("--camera", choices=("webcam", "robot"))
    parser.add_argument("--detector", choices=("person", "motion"), default="person")
    parser.add_argument("--robot", action="store_true")
    parser.add_argument("--no-track", action="store_true", help="대화·환영 모드 사람 추적 끄기")
    parser.add_argument("--max-seconds", type=float, help="짧은 동작 확인 후 종료")
    parser.add_argument("--host", help="로봇 호스트 이름 또는 IP (기본: 자동 검색)")
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    if args.camera is None:
        args.camera = "robot" if args.robot else "webcam"
    if not 1 <= (args.seconds if args.seconds is not None else args.minutes * 60) <= 3600:
        parser.error("길이는 1~3600초여야 합니다.")
    if args.max_seconds is not None and args.max_seconds <= 0:
        parser.error("--max-seconds는 0보다 커야 합니다.")
    Controller(args).run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("중지했습니다.")
    except Exception as exc:
        print(f"오류: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
