"""Offline entrance greeting: local person approach detection and cached MP3 playback."""

import argparse
from collections import deque
from contextlib import nullcontext
import random
import sys
import time

import numpy as np

from common import ROOT, audio_path, lines
from play_lines import play
from robot_host import resolve_robot_host


def parse_region(value: str) -> tuple[float, float, float, float]:
    try:
        region = tuple(float(part) for part in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--region은 x1,y1,x2,y2 형식입니다.") from exc
    if len(region) != 4 or not (0 <= region[0] < region[2] <= 1 and 0 <= region[1] < region[3] <= 1):
        raise argparse.ArgumentTypeError("--region 좌표는 0~1이고 x1<x2, y1<y2여야 합니다.")
    return region


def region_pixels(region, width, height):
    return (int(region[0] * width), int(region[1] * height),
            int(region[2] * width), int(region[3] * height))


def inside(box, region):
    cx = (box[0] + box[2]) / 2
    cy = (box[1] + box[3]) / 2
    return region[0] <= cx <= region[2] and region[1] <= cy <= region[3]


class ApproachDetector:
    def __init__(self, sensitivity):
        self.history = deque()
        self.sensitivity = sensitivity
        self.last_center = None

    def update(self, boxes, now, width, height):
        if not boxes:
            self.history.clear()
            self.last_center = None
            return None
        # Follow the nearest box center across frames, without identifying anyone.
        if self.last_center is None:
            box = max(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
        else:
            box = min(boxes, key=lambda b: ((b[0] + b[2]) / 2 - self.last_center[0]) ** 2
                      + ((b[1] + b[3]) / 2 - self.last_center[1]) ** 2)
        center = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        if self.last_center and ((center[0] - self.last_center[0]) / width) ** 2 + ((center[1] - self.last_center[1]) / height) ** 2 > 0.12 ** 2:
            self.history.clear()
        self.last_center = center
        self.history.append((now, (box[2] - box[0]) * (box[3] - box[1])))
        while self.history and now - self.history[0][0] > 1.5:
            self.history.popleft()
        if len(self.history) < 3 or now - self.history[0][0] < 0.8:
            return None
        baseline = self.history[0][1]
        growth = self.history[-1][1] / max(1, baseline) - 1
        if growth >= 0.32 - 0.24 * self.sensitivity:
            self.history.clear()
            return center
        return None


class MotionDetector:
    def __init__(self, cv2, sensitivity):
        self.cv2 = cv2
        self.background = cv2.createBackgroundSubtractorMOG2(history=120, varThreshold=32, detectShadows=False)
        self.started = time.monotonic()
        self.sensitivity = sensitivity

    def update(self, frame, region):
        cv2 = self.cv2
        mask = self.background.apply(frame)
        if time.monotonic() - self.started < 2:
            return None, []
        mask = cv2.medianBlur(mask, 7)
        x1, y1, x2, y2 = region
        roi = mask[y1:y2, x1:x2]
        contours, _ = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = []
        for contour in contours:
            if cv2.contourArea(contour) < (x2 - x1) * (y2 - y1) * (0.06 - 0.05 * self.sensitivity):
                continue
            x, y, w, h = cv2.boundingRect(contour)
            boxes.append((x + x1, y + y1, x + x1 + w, y + y1 + h))
        if not boxes:
            return None, []
        box = max(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
        return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), boxes


class PersonDetector:
    """Run YOLO11 nano ONNX on CPU without importing PyTorch."""

    def __init__(self, cv2):
        import onnxruntime as ort

        model_path = ROOT / "yolo11n.onnx"
        if not model_path.is_file():
            raise RuntimeError("yolo11n.onnx가 없습니다. scripts/README.md의 모델 다운로드 명령을 실행하세요.")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(model_path), options, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.cv2 = cv2

    def detect(self, frame, confidence=0.35):
        cv2 = self.cv2
        height, width = frame.shape[:2]
        image = cv2.cvtColor(cv2.resize(frame, (640, 640)), cv2.COLOR_BGR2RGB)
        tensor = np.ascontiguousarray(image.transpose(2, 0, 1)[None], dtype=np.float32) / 255.0
        output = self.session.run(None, {self.input_name: tensor})[0][0].T
        people = output[output[:, 4] >= confidence]
        if len(people) == 0:
            return []
        xywh = people[:, :4].copy()
        xywh[:, 0] -= xywh[:, 2] / 2
        xywh[:, 1] -= xywh[:, 3] / 2
        keep = cv2.dnn.NMSBoxes(xywh.tolist(), people[:, 4].tolist(), confidence, 0.45)
        boxes = []
        for index in np.array(keep).reshape(-1):
            x, y, w, h = xywh[index]
            boxes.append((max(0, int(x * width / 640)), max(0, int(y * height / 640)),
                          min(width, int((x + w) * width / 640)),
                          min(height, int((y + h) * height / 640))))
        return boxes


def greet(robot, center, width, height, path):
    if robot is None:
        play(path)
        return
    robot.goto_target(antennas=[0.35, -0.35], duration=0.25, body_yaw=None)
    robot.goto_target(antennas=[-0.35, 0.35], duration=0.25)
    robot.goto_target(antennas=[0, 0], duration=0.25)
    robot.media.play_sound(str(path.resolve()))


def main(stop_event=None, argv=None):
    parser = argparse.ArgumentParser(description="리치 체크인 환영 모드")
    parser.add_argument("--camera", choices=("webcam", "robot"))
    parser.add_argument("--robot", action="store_true", help="로봇 머리·안테나·스피커 사용")
    parser.add_argument("--no-track", action="store_true", help="사람을 향한 머리 추적 끄기")
    parser.add_argument("--no-body", action="store_true", help="사람 추적 중 몸통 회전 끄기")
    parser.add_argument("--no-dance", action="store_true", help="사람이 없을 때 춤추기 끄기")
    parser.add_argument("--host", help="로봇 호스트 이름 또는 IP (기본: 자동 검색)")
    parser.add_argument("--detector", choices=("person", "motion"), default="person")
    parser.add_argument("--region", type=parse_region, default=(0.0, 0.0, 1.0, 1.0), metavar="x1,y1,x2,y2")
    parser.add_argument("--sensitivity", type=float, default=0.5, help="0~1; 클수록 더 민감")
    parser.add_argument("--cooldown", type=float, default=8.0, help="인사 간격(초)")
    parser.add_argument("--preview", action="store_true", help="영역과 감지 박스를 화면에 표시")
    parser.add_argument("--max-seconds", type=float, help="테스트용 실행 제한")
    parser.add_argument("--no-wave", action="store_true", help="손인사 감지 끄기")
    parser.add_argument("--wave-cooldown", type=float, default=10.0, help="손인사 간격(초)")
    args = parser.parse_args(argv)
    if args.camera is None:
        args.camera = "robot" if args.robot else "webcam"
    if not 0 <= args.sensitivity <= 1 or args.cooldown < 0 or args.wave_cooldown < 0 or (args.max_seconds is not None and args.max_seconds <= 0):
        parser.error("sensitivity는 0~1, cooldown은 0 이상, max-seconds는 0 초과여야 합니다.")

    import cv2
    directory = ROOT / "audio" / "welcome"
    entries = [(number, name, spoken, audio_path(number, name, directory))
               for number, name, spoken in lines(ROOT / "agent" / "welcome-lines.ko.md")]
    missing = [str(path) for _, _, _, path in entries if not path.is_file() or path.stat().st_size == 0]
    if missing:
        raise RuntimeError("환영 MP3가 없습니다. 먼저 make_lines.py --welcome 실행: " + ", ".join(missing))
    wave_pose = wave_detector = None
    if not args.no_wave and args.camera == "robot":
        from wave_gesture import PoseDetector, WaveDetector
        wave_pose = PoseDetector(cv2)
        wave_detector = WaveDetector(args.wave_cooldown)
        for name in ("01.mp3", "02.mp3"):
            if not (ROOT / "audio" / "wave" / name).is_file():
                raise RuntimeError("손인사 MP3 없음: make_wave_lines.py 실행")
        print("손인사 감지: YOLO11n-pose ONNX, CPU 1 thread", flush=True)

    person = None
    if args.detector == "person":
        person = PersonDetector(cv2) if not wave_pose else None
        approach = ApproachDetector(args.sensitivity)
        print("사람 감지기 초기화: " + ("YOLO11n-pose" if wave_pose else "YOLO11n") + " ONNX, CPU 1 thread", flush=True)
    else:
        motion = MotionDetector(cv2, args.sensitivity)
        print("움직임 감지기 초기화: OpenCV MOG2", flush=True)

    use_robot = args.robot or args.camera == "robot"
    connected = False
    try:
        if use_robot:
            from reachy_mini import ReachyMini
            host, source = resolve_robot_host(args.host)
            print(f"사용 호스트: {host} ({source})", flush=True)
            connection = ReachyMini(host=host, connection_mode="network", media_backend="default", timeout=15)
        else:
            connection = nullcontext(None)
        with connection as mini:
            connected = True
            gaze = None
            if args.robot:
                from person_gaze import PersonGaze, neutral
                if args.camera == "robot" and args.detector == "person" and not args.no_track:
                    gaze = PersonGaze(mini, log=True, body=not args.no_body)
                else:
                    neutral(mini)
            cap = None
            if args.camera == "webcam":
                cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) if sys.platform == "win32" else cv2.VideoCapture(0)
                if not cap.isOpened():
                    raise RuntimeError("노트북 웹캠을 열 수 없습니다. 카메라 권한과 사용 중인 앱을 확인하세요.")
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            print(f"카메라 시작: {args.camera}; 로봇 동작: {'켜짐' if args.robot else '꺼짐'}", flush=True)
            start = time.monotonic()
            first_frame_deadline = start + 8.0
            last_greeting = -float("inf")
            last_line = None
            last_wave_line = 0
            wave_target = None
            wave_target_until = 0.0
            frames = 0
            # 사람이 없을 때 짧은 춤(약 2초짜리)을 이어서 춘다. 춤이 끝나야 인사·추적을 재개한다.
            dances, dance_thread, last_person = None, None, time.monotonic()
            if args.robot and not args.no_dance:
                try:
                    import threading
                    from reachy_mini.motion.recorded_move import RecordedMoves
                    dances = RecordedMoves("pollen-robotics/reachy-mini-dances-library")
                except Exception as exc:
                    print(f"춤 라이브러리 없음: {exc}", flush=True)
            idle_dances = ("side_to_side_sway", "groovy_sway_and_roll", "yeah_nod", "uh_huh_tilt",
                           "head_tilt_roll", "pendulum_swing", "chin_lead", "simple_nod")
            try:
                while (not stop_event or not stop_event.is_set()) and (args.max_seconds is None or time.monotonic() - start < args.max_seconds):
                    ok, frame = cap.read() if cap else (True, mini.media.get_frame())
                    if not ok or frame is None:
                        if frames == 0 and (cap or time.monotonic() >= first_frame_deadline):
                            raise RuntimeError("카메라에서 프레임을 받을 수 없습니다.")
                        time.sleep(0.05)
                        continue
                    frames += 1
                    height, width = frame.shape[:2]
                    region = region_pixels(args.region, width, height)
                    boxes = []
                    if args.detector == "person":
                        poses = wave_pose.detect(frame) if wave_pose else []
                        boxes = [box for box, _ in poses] if wave_pose else person.detect(frame)
                        boxes = [box for box in boxes if inside(box, region)]
                        center = approach.update(boxes, time.monotonic(), width, height)
                    else:
                        center, boxes = motion.update(frame, region)
                    now = time.monotonic()
                    waved = wave_detector.update(poses if args.detector == "person" else wave_pose.detect(frame), now) if wave_detector else None
                    if waved:
                        print(f"손인사 감지: {waved}", flush=True)
                        wave_target, wave_target_until = waved, now + 3.0
                        last_wave_line = 1 + last_wave_line % 2
                        wave_file = ROOT / "audio" / "wave" / f"0{last_wave_line}.mp3"
                        greet(mini if args.robot else None, None, width, height, wave_file)
                        last_greeting = now
                    # 붐비는 행사장에서는 늘 누군가 보이므로, "다가오는 사람"이 없을 때 춘다
                    if center:
                        last_person = now
                    dancing = dance_thread is not None and dance_thread.is_alive()
                    if dances and not dancing and not center and now - last_person > 3.0 and now - last_greeting > 4.0:
                        name = random.choice(idle_dances)
                        swing = random.choice((-1, 1)) * 0.45  # 공식 춤은 몸통을 안 쓰므로 춤 사이에 몸통을 좌우로 흔든다

                        def dance_once(n=name, yaw=swing):
                            mini.play_move(dances.get(n), initial_goto_duration=0.4, sound=False)
                            mini.goto_target(body_yaw=yaw, duration=0.7)
                            mini.goto_target(body_yaw=-yaw, duration=0.9)
                            mini.goto_target(body_yaw=0.0, duration=0.6)

                        dance_thread = threading.Thread(target=dance_once, daemon=True)
                        dance_thread.start()
                        dancing = True
                    if dancing:
                        continue
                    if gaze:
                        if wave_target and boxes and now < wave_target_until:
                            cx = (wave_target[0]+wave_target[2])/2
                            cy = (wave_target[1]+wave_target[3])/2
                            tracked = [min(boxes, key=lambda b: ((b[0]+b[2])/2-cx)**2 + ((b[1]+b[3])/2-cy)**2)]
                        else:
                            tracked = boxes
                        gaze.update(tracked, width, height)
                    if center and not waved and now - last_greeting >= args.cooldown:
                        choices = [entry for entry in entries if entry[0] != last_line]
                        number, _, spoken, path = random.choice(choices)
                        last_line = number
                        last_greeting = now
                        print(f"환영 {number}: {spoken}", flush=True)
                        greet(mini if args.robot else None, center, width, height, path)
                    if args.preview:
                        cv2.rectangle(frame, region[:2], region[2:], (255, 200, 0), 2)
                        for box in boxes:
                            cv2.rectangle(frame, box[:2], box[2:], (0, 255, 0), 2)
                        cv2.imshow("Reachy Welcome - Q to quit", frame)
                        if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                            break
                    if frames % 100 == 0:
                        print(f"프레임 처리: {frames}", flush=True)
            finally:
                if args.robot:
                    neutral(mini)
                if cap:
                    cap.release()
                if args.preview:
                    cv2.destroyAllWindows()
                print(f"종료: {frames} 프레임 처리", flush=True)
    except Exception as exc:
        if use_robot and not connected:
            raise RuntimeError("Reachy Mini Wireless에 연결하지 못했습니다. 전원, 같은 Wi-Fi, 데몬을 확인하세요.") from exc
        raise


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("중지했습니다.")
    except Exception as exc:
        print(f"오류: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
