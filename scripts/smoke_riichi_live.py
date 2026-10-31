"""Online text smoke test of the actual published tool and controller."""
from argparse import Namespace
import queue
import time

from riichi import Controller


def pump(controller, until, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            kind, value = controller.events.get(timeout=0.2)
        except queue.Empty:
            continue
        controller.handle(kind, value)
        if until(kind, value):
            return value
    raise TimeoutError("Expected controller event did not arrive")


def main():
    args = Namespace(mode="conversation", minutes=3, seconds=None, text=True,
                     offline=True, camera="webcam", detector="person", robot=False, preview=False)
    controller = Controller(args)
    try:
        controller.switch("conversation")
        deadline = time.monotonic() + 15
        while controller.session._ws is None and time.monotonic() < deadline:
            time.sleep(0.1)
        assert controller.session._ws is not None
        controller.session.send_user_message("타이머 모드 활성화")
        pump(controller, lambda k, v: k == "tool")
        assert controller.mode == "timer" and controller.session is None
        controller.handle("transcript", "제출 마감 언제야?")
        assert controller.mode == "timer" and controller.session is None
        controller.handle("transcript", "타이머 모드 해제")
        assert controller.mode == "conversation" and controller.session is not None
        deadline = time.monotonic() + 15
        while controller.session._ws is None and time.monotonic() < deadline:
            time.sleep(0.1)
        controller.session.send_user_message("제출 마감 언제야?")
        answer = pump(controller, lambda k, v: k == "answer" and
                      ("세 시 반" in v[1] or "3시 30분" in v[1] or "3:30" in v[1]))
        assert answer[0] == controller.session_epoch
        assert "세 시 반" in answer[1] or "3시 30분" in answer[1] or "3:30" in answer[1]
        print("PASS: tool -> timer disconnected -> ignored -> exit -> conversation answer")
        controller.handle("switch", "timer")
        assert controller.mode == "timer" and controller.session is None
        controller.handle("switch", "conversation")
        assert controller.mode == "conversation" and controller.session is not None
        print("PASS: hotkey switch events")
        deadline = time.monotonic() + 15
        while controller.session._ws is None and time.monotonic() < deadline:
            time.sleep(0.1)
        controller.session.send_user_message("타이머 모드 5분")
        pump(controller, lambda k, v: k == "tool")
        assert controller.mode == "timer" and controller.session is None
        assert controller.length == 300 and controller.state == "running"
        print("PASS: spoken five-minute length and start")
    finally:
        controller.disconnect()


if __name__ == "__main__":
    main()
