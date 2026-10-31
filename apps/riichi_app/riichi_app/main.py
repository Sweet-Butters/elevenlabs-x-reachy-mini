"""Reachy Mini Wireless booth app: daemon-owned robot, phone controls."""
import json
import queue
import random
import re
import signal
import threading
import time
from pathlib import Path
from urllib.request import Request, urlopen

from pydantic import BaseModel
from reachy_mini import ReachyMini, ReachyMiniApp
from reachy_mini.utils import create_head_pose

from .audio import ScribeListener, Speaker
from .emotion_motion import EmotionMotion
from .secrets import api_key, save_api_key
from .wake_gate import WakeGate


class Command(BaseModel):
    action: str
    value: int | bool | None = None


class KeyInput(BaseModel):
    key: str


class RiichiApp(ReachyMiniApp):
    custom_app_url = "http://0.0.0.0:8042"

    def __init__(self):
        super().__init__()
        self.config = json.loads((Path(__file__).parent / "config.json").read_text(encoding="utf-8"))
        self.events, self.errors = queue.Queue(), queue.Queue()
        self.lock = threading.RLock()
        self.mode, self.last_transcript, self.last_error = "conversation", "", ""
        self.tracking, self.dance = "준비 중", True
        self.length = self.current_length = int(self.config.get("timer_seconds", 300))
        self.elapsed, self.resumed_at, self.timer_state, self.timer_number = 0.0, 0.0, "ready", 1
        self.fired = set()
        self.robot = self.speaker = self.listener = self.session = self.motion = None
        self.ready = False
        self.gate, self.initial_response_seen = WakeGate(5), False
        self.vision = self.gaze = self.approach = None
        self.next_detect = self.last_greeting = 0.0
        self.last_person, self.last_line = time.monotonic(), -1
        self.last_turn = 0.0
        self.run_stop = threading.Event()
        self._routes()

    def _routes(self):
        @self.settings_app.get("/api/status")
        def status():
            if not self.ready:
                from fastapi import HTTPException
                raise HTTPException(503, "로봇 연결 대기 중")
            with self.lock:
                elapsed = self.elapsed + (time.monotonic() - self.resumed_at if self.timer_state == "running" else 0)
                return {"mode": self.mode, "last_transcript": self.last_transcript,
                        "error": self.last_error, "tracking": self.tracking, "dance": self.dance,
                        "timer_state": self.timer_state, "remaining": max(0, round(self.current_length - elapsed)),
                        "length": self.length, "timer_number": self.timer_number, "key_saved": self._has_key()}

        @self.settings_app.post("/api/command")
        def command(item: Command):
            from fastapi import HTTPException
            if not self.ready:
                raise HTTPException(503, "로봇 연결 대기 중")
            if item.action not in ("welcome", "conversation", "timer", "start_next", "pause",
                                   "reset", "length", "dance", "volume", "test"):
                raise HTTPException(400, "알 수 없는 명령")
            if item.action in ("length", "volume"):
                low, high = (1, 3600) if item.action == "length" else (0, 100)
                if type(item.value) is not int or not low <= item.value <= high:
                    raise HTTPException(400, f"{low}~{high} 범위를 입력해 주세요")
            if item.action == "dance" and type(item.value) is not bool:
                raise HTTPException(400, "춤 설정이 올바르지 않습니다")
            self.events.put((item.action, item.value))
            return {"queued": True}

        @self.settings_app.post("/api/key")
        def key(item: KeyInput):
            try:
                save_api_key(item.key)
            except ValueError:
                from fastapi import HTTPException
                raise HTTPException(400, "API key 형식이 올바르지 않습니다")
            return {"saved": True}

    def _has_key(self):
        try:
            api_key()
            return True
        except RuntimeError:
            return False

    def _error(self, message):
        try:
            message = message.replace(api_key(), "[redacted]")
        except RuntimeError:
            pass
        with self.lock:
            self.last_error = message[:300]
        print(message, flush=True)

    def _start_conversation(self):
        from elevenlabs.client import ElevenLabs
        from elevenlabs.conversational_ai.conversation import Conversation, ClientTools, ConversationInitiationData
        tools = ClientTools()
        def set_mode(parameters):
            self.events.put(("agent_mode", (parameters.get("mode"), parameters.get("duration_seconds"))))
            return "Switching mode."
        tools.register("set_mode", set_mode)
        config = ConversationInitiationData(conversation_config_override={"conversation": {"text_only": True}})
        self.initial_response_seen = False
        def response(answer):
            if not self.initial_response_seen:
                self.initial_response_seen = True
                return
            if self.mode == "conversation":
                self.speaker.say(answer, done=self.gate.answered)
        self.session = Conversation(ElevenLabs(api_key=api_key()), self.config["agent_id"],
                                    requires_auth=True, client_tools=tools, config=config,
                                    callback_agent_response=response)
        self.session.start_session()
        self.listener = ScribeListener(self.robot, self.events, self.config.get("stt_language", "auto"))
        self.listener.start()

    def _close_session(self, session):
        """Do not let a stalled ElevenLabs socket hold up app shutdown."""
        def close():
            try:
                session.end_session()
                session.wait_for_session_end()
            except Exception as exc:
                self._error("대화 종료: " + str(exc))

        worker = threading.Thread(target=close, daemon=True)
        worker.start()
        worker.join(timeout=3)
        if worker.is_alive():
            self._error("대화 종료 시간 초과")

    def _switch(self, mode):
        if mode == self.mode and self.listener is not None:
            return
        if self.motion:
            self.motion.pause()
        if self.listener:
            self.listener.close()
            self.listener = None
        if self.session:
            session, self.session = self.session, None
            self._close_session(session)
        with self.lock:
            self.mode = mode
            if mode == "timer":
                self.timer_state, self.elapsed, self.fired = "ready", 0.0, set()
        if mode == "conversation":
            try:
                self._start_conversation()
            except Exception as exc:
                self._error("대화 연결: " + str(exc))
        if mode == "welcome":
            self.last_person = time.monotonic()

    def _speak_timer(self, kind, seconds=0):
        from .timer_audio import phrase
        self.speaker.say(phrase(kind, seconds, self.config["language"]))

    def _timer_command(self, action):
        with self.lock:
            state = self.timer_state
            if action == "start_next" and state in ("ready", "done"):
                if state == "done":
                    self.timer_number += 1
                self.current_length = self.length
                self.elapsed, self.fired = 0.0, set()
                self.resumed_at, self.timer_state = time.monotonic(), "running"
                self._speak_timer("start", self.current_length)
            elif action == "pause":
                if state == "running":
                    self.elapsed += time.monotonic() - self.resumed_at
                    self.timer_state = "paused"
                elif state == "paused":
                    self.resumed_at, self.timer_state = time.monotonic(), "running"
            elif action == "reset":
                self.timer_state, self.elapsed, self.fired = "ready", 0.0, set()

    def _tick_timer(self):
        if self.mode != "timer" or self.timer_state != "running":
            return
        remaining = self.current_length - self.elapsed - (time.monotonic() - self.resumed_at)
        from .timer_audio import announcement_schedule
        for point in announcement_schedule(self.current_length):
            if remaining <= point and point not in self.fired:
                self.fired.add(point)
                if point == 0:
                    self.timer_state, self.elapsed = "done", self.current_length
                self._speak_timer("up" if point == 0 else "left", point)

    def _init_vision(self):
        try:
            import cv2
            from .person_gaze import PersonGaze
            from .vision import ApproachDetector, PersonDetector
            self.vision, self.approach = PersonDetector(cv2), ApproachDetector()
            self.gaze = PersonGaze(self.robot, body=True)
            self.tracking = "YOLO 사람 추적"
        except Exception as exc:
            self.vision, self.tracking = None, "감지 없이 정기 인사"
            self._error("사람 추적 사용 불가: " + str(exc))

    def _tick_welcome(self):
        now = time.monotonic()
        if self.vision and now >= self.next_detect:
            self.next_detect = now + 1.0 / max(0.2, min(10, float(self.config.get("detection_fps", 2))))
            try:
                frame = self.robot.media.get_frame()
                if frame is not None:
                    height, width = frame.shape[:2]
                    boxes = self.vision.detect(frame)
                    if boxes:
                        self.motion.pause()
                    self.gaze.update(boxes, width, height)
                    if boxes:
                        self.last_person = now
                    if self.approach.update(boxes, now, width, height):
                        self._greet(now)
            except Exception as exc:
                self.vision, self.tracking = None, "감지 없이 정기 인사"
                self._error("사람 추적 중단: " + str(exc))
        if not self.vision and now - self.last_greeting >= self.config.get("fallback_greeting_seconds", 90):
            self._greet(now)
        self.motion.tick(self.dance and now - self.last_person > 5 and not self.speaker.busy.is_set())

    def _greet(self, now):
        if now - self.last_greeting < 8 or self.speaker.busy.is_set():
            return
        self.last_greeting = now
        lines = self.config.get("greetings", [])
        if not lines:
            return
        self.last_line = random.choice([i for i in range(len(lines)) if i != self.last_line] or [0])
        self.motion.pause()
        try:
            self.robot.goto_target(antennas=[0.35, -0.35], duration=0.25)
            self.robot.goto_target(antennas=[-0.35, 0.35], duration=0.25)
            self.robot.goto_target(antennas=[0, 0], duration=0.25)
        except Exception as exc:
            self._error("인사 동작: " + str(exc))
        self.speaker.say(lines[self.last_line])

    def _transcript(self, value):
        if isinstance(value, dict):
            language, value = value.get("language_code"), value.get("text", "")
        else:
            language = None
        with self.lock:
            self.last_transcript = value
        if self.mode == "conversation":
            if not value.strip() or self.speaker.busy.is_set() or time.monotonic() - self.last_turn < 2.0:
                return
            explicit_wake = re.search(r"(?:hey\s+reachy|리\s*치\s*야)", value, re.I)
            english = language == "en" or (language not in ("ko", "en") and
                len(re.findall(r"[A-Za-z]+", value)) >= 3 and not re.search(r"[가-힣]", value))
            if english and not explicit_wake:
                words = re.findall(r"[A-Za-z]+", value)
                if (len(words) < 3 or len(set(word.lower() for word in words)) <= 1
                        or value.strip().lower() in ("thank you very much", "one two three")):
                    return
                decision, message = "send", value.strip()
            else:
                decision, message = self.gate.decide(value)
            if decision == "ack":
                self.speaker.say("네, 말씀해 주세요.")
            elif decision == "send" and self.session:
                deadline = time.monotonic() + 10
                while self.session._ws is None and time.monotonic() < deadline and not self.run_stop.is_set():
                    self.run_stop.wait(0.05)
                if self.run_stop.is_set():
                    return
                if self.session._ws:
                    greeting_deadline = time.monotonic() + 6
                    while not self.initial_response_seen and time.monotonic() < greeting_deadline and not self.run_stop.is_set():
                        self.run_stop.wait(0.05)
                    if self.run_stop.is_set():
                        return
                    self.initial_response_seen = True
                    self.last_turn = time.monotonic()
                    self.motion.pause()
                    self.speaker.busy.set()
                    try:
                        response_language = "English" if english or language == "en" else "Korean"
                        self.session.send_contextual_update(f"The current visitor used {response_language}. Reply in {response_language}. Keep the reply concise.")
                    except Exception:
                        pass
                    self.session.send_user_message(message)
        elif self.mode == "timer":
            from .timer_audio import duration_from_text
            length = duration_from_text(value)
            if length:
                self.length = length

    def _event(self, action, value):
        if action in ("welcome", "conversation", "timer"):
            self._switch(action)
        elif action == "agent_mode":
            mode, length = value
            if mode in ("welcome", "conversation", "timer"):
                if length is not None and 1 <= int(length) <= 3600:
                    self.length = int(length)
                self._switch(mode)
        elif action in ("start_next", "pause", "reset") and self.mode == "timer":
            self._timer_command(action)
        elif action == "length":
            with self.lock:
                self.length = value
        elif action == "dance":
            self.dance = value
        elif action == "volume":
            request = Request("http://127.0.0.1:8000/api/volume/set",
                              data=json.dumps({"volume": value}).encode(),
                              headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(request, timeout=3):
                pass
        elif action == "test":
            self.speaker.say("Hi! I'm Reachy. Can you hear me? 안녕하세요, 리치 목소리 들리세요?")
        elif action == "transcript":
            self._transcript(value)
        elif action == "error":
            self._error(value)

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event):
        self.run_stop = stop_event
        self.robot = reachy_mini
        # 데몬이 앱 전환 뒤 모터를 꺼 둔 채 시작하는 경우가 있어, 시작할 때 깨운다
        try:
            reachy_mini.enable_motors()
            reachy_mini.wake_up()
        except Exception as exc:
            self._error(f"모터 깨우기 실패: {exc}")
        self.motion = EmotionMotion(reachy_mini, self.errors)
        self.motion.start()
        self.speaker = Speaker(reachy_mini, self.config, self.errors, before_say=self.motion.pause)
        try:
            self._event("volume", 100)
        except Exception as exc:
            self._error("볼륨 설정: " + str(exc))
        self._init_vision()
        self._switch("conversation")
        self.ready = True
        try:
            while not stop_event.is_set():
                try:
                    while True:
                        self._error(self.errors.get_nowait())
                except queue.Empty:
                    pass
                try:
                    action, value = self.events.get(timeout=0.05)
                    try:
                        self._event(action, value)
                    except Exception as exc:
                        self._error(action + ": " + str(exc))
                except queue.Empty:
                    pass
                if self.mode == "welcome":
                    self._tick_welcome()
                elif self.mode == "conversation":
                    self._tick_conversation()
                elif self.mode == "timer":
                    self._tick_timer()
        finally:
            self.ready = False
            stop_event.set()
            self.motion.close()
            cleanup = []
            if self.listener:
                cleanup.append((self.listener.close, ()))
                self.listener = None
            if self.session:
                cleanup.append((self._close_session, (self.session,)))
                self.session = None
            if self.speaker:
                cleanup.append((self.speaker.close, ()))
            workers = [threading.Thread(target=fn, args=args, daemon=True) for fn, args in cleanup]
            for worker in workers:
                worker.start()
            deadline = time.monotonic() + 3
            for worker in workers:
                worker.join(max(0, deadline - time.monotonic()))

    def _tick_conversation(self):
        now = time.monotonic()
        if self.speaker.busy.is_set() and self.last_turn and now - self.last_turn > 25:
            self.speaker.busy.clear()
            self.last_turn = 0
            self._error("대화 응답 시간 초과")
        if self.speaker.busy.is_set() or now - self.speaker.last_done < 0.6:
            if self.vision and now >= self.next_detect:
                self._detect(track=True)
            return
        self.motion.tick(self.dance)

    def _detect(self, track=False):
        now = time.monotonic()
        self.next_detect = now + 1.0 / max(0.2, min(10, float(self.config.get("detection_fps", 1))))
        try:
            frame = self.robot.media.get_frame()
            if frame is None:
                return []
            height, width = frame.shape[:2]
            boxes = self.vision.detect(frame)
            if track:
                self.gaze.update(boxes, width, height)
            return boxes
        except Exception as exc:
            self.vision, self.tracking = None, "감지 없이 정기 인사"
            self._error("사람 추적 중단: " + str(exc))
            return []

if __name__ == "__main__":
    app = RiichiApp()
    signal.signal(signal.SIGINT, lambda _signum, _frame: app.stop())
    try:
        app.wrapped_run()
    except KeyboardInterrupt:
        app.stop()
