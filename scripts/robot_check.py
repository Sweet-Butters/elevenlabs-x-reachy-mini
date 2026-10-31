"""Quick, bounded Reachy Mini Wireless check. No camera or microphone data is saved."""

import argparse
import os
from pathlib import Path
import queue
import socket
import sys
import threading
import time

from robot_host import resolve_robot_host


ROOT = Path(__file__).resolve().parents[1]
STEPS = ("network", "connect", "head", "antennas", "camera", "speaker", "microphone")
LABELS = {
    "network": "네트워크", "connect": "SDK 연결", "head": "머리",
    "antennas": "안테나", "camera": "카메라", "speaker": "로봇 스피커",
    "microphone": "로봇 마이크",
}
HINTS = {
    "network": "로봇 전원과 노트북의 같은 휴대폰 핫스팟 연결을 확인하세요. .local 이름이 안 잡히면 로봇 IP로 --host를 지정하고, 핫스팟의 기기 간 통신 차단 설정을 확인하세요.",
    "connect": "로봇 데몬과 SDK 버전을 확인하세요. Windows에서 WebSocket은 열리지만 여기서 멈추면 노트북의 GStreamer 초기화도 확인하세요.",
    "head": "머리 주변 장애물을 치우고 조립 상태와 모터 전원을 확인하세요.",
    "antennas": "안테나가 걸리지 않는지와 모터 전원을 확인하세요.",
    "camera": "카메라 연결과 로봇 미디어 서비스(WebRTC)를 확인하세요.",
    "speaker": "MP3 파일, 로봇 볼륨, 스피커와 미디어 서비스를 확인하세요. PASS여도 실제 소리를 들어 확인하세요.",
    "microphone": "로봇 마이크 연결과 미디어 서비스를 확인하고, 로봇 가까이에서 말하며 다시 실행하세요.",
}


def check_network(host, timeout):
    addresses = socket.getaddrinfo(host, 8000, type=socket.SOCK_STREAM)
    if not addresses:
        raise RuntimeError("호스트 주소를 찾지 못했습니다")
    with socket.create_connection((host, 8000), timeout=min(timeout, 2.0)):
        pass
    return f"{host}:8000 연결 가능"


def check_robot(step, robot, show):
    from reachy_mini.utils import create_head_pose

    if step == "head":
        try:
            robot.goto_target(head=create_head_pose(pitch=5, degrees=True), duration=1.2)
        finally:
            robot.goto_target(head=create_head_pose(degrees=True), duration=1.2)
        return "작게 끄덕이고 중립 위치 복귀"
    if step == "antennas":
        try:
            robot.goto_target(antennas=[0.18, -0.18], duration=1.2)
            robot.goto_target(antennas=[-0.18, 0.18], duration=1.2)
        finally:
            robot.goto_target(antennas=[0.0, 0.0], duration=1.2)
        return "작게 흔들고 중립 위치 복귀"
    if step == "camera":
        frame = robot.media.get_frame()
        if frame is None:
            raise RuntimeError("카메라 프레임이 없습니다")
        height, width = frame.shape[:2]
        if show:
            import cv2
            try:
                cv2.imshow("Reachy Mini camera (3 seconds)", frame)
                cv2.waitKey(3000)
            finally:
                cv2.destroyAllWindows()
        return f"{width}x{height} 프레임 수신" + (" · 화면 표시" if show else "")
    if step == "speaker":
        clips = sorted((ROOT / "audio" / "welcome").glob("01-*.mp3"))
        if not clips:
            clips = sorted((ROOT / "audio").rglob("*.mp3"))
        clips = [clip for clip in clips if clip.stat().st_size > 0]
        if not clips:
            raise RuntimeError("재생할 MP3가 없습니다")
        robot.media.play_sound(str(clips[0].resolve()))
        return f"재생 요청 전송: {clips[0].name} (실제 소리를 들어 확인)"
    if step == "microphone":
        media = robot.media
        if media.audio is None or not all(hasattr(media, name) for name in
                                          ("start_recording", "get_audio_sample", "stop_recording")):
            return ("SKIP", "현재 미디어 백엔드에서 로봇 마이크를 사용할 수 없습니다")
        import numpy as np
        peak = 0.0
        count = 0
        media.start_recording()
        try:
            until = time.monotonic() + 2.0
            while time.monotonic() < until:
                sample = media.get_audio_sample()
                if sample is not None and sample.size:
                    peak = max(peak, float(np.max(np.abs(sample))))
                    count += sample.size
                else:
                    time.sleep(0.03)
        finally:
            media.stop_recording()
        if count == 0:
            return ("SKIP", "2초 동안 마이크 샘플이 없어 수신을 확인할 수 없습니다")
        return f"2초 수신 · 피크 {peak:.3f} (정규화 레벨)"
    raise ValueError(f"알 수 없는 단계: {step}")


def network_worker(result, host, timeout):
    try:
        result.append(("PASS", check_network(host, timeout)))
    except Exception as exc:
        result.append(("FAIL", f"{type(exc).__name__}: {exc}"))


def run_network(host, timeout):
    result = []
    thread = threading.Thread(target=network_worker, args=(result, host, timeout), daemon=True)
    thread.start()
    limit = min(timeout, 4.0)
    thread.join(limit)
    return ("FAIL", f"{limit:g}초 제한 시간 초과") if thread.is_alive() else result[0]


def robot_worker(events, steps, host, timeout, show):
    connected = False
    try:
        from reachy_mini import ReachyMini

        with ReachyMini(host=host, connection_mode="network", media_backend="default",
                        timeout=max(15.0, timeout), log_level="WARNING") as robot:
            connected = True
            events.put(("connect", "PASS", "Reachy Mini 데몬 연결 성공"))
            for step in steps:
                try:
                    value = check_robot(step, robot, show)
                    status, detail = value if isinstance(value, tuple) else ("PASS", value)
                except Exception as exc:
                    status, detail = "FAIL", f"{type(exc).__name__}: {exc}"
                events.put((step, status, detail))
    except Exception as exc:
        if not connected:
            events.put(("connect", "FAIL", f"{type(exc).__name__}: {exc}"))
        else:
            events.put(("close", "FAIL", f"{type(exc).__name__}: {exc}"))


def main():
    parser = argparse.ArgumentParser(description="Reachy Mini Wireless 조립 직후 점검")
    parser.add_argument("--host", help="로봇 호스트 이름 또는 IP (기본: 자동 검색)")
    parser.add_argument("--step", choices=STEPS, help="한 단계만 실행")
    parser.add_argument("--timeout", type=float, default=20.0, help="단계별 제한 시간, 초 (기본: 20)")
    parser.add_argument("--show", action="store_true", help="카메라 프레임을 3초간 화면에 표시")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout은 0보다 커야 합니다")

    selected = (args.step,) if args.step else STEPS
    results = {}
    timed_out = False
    try:
        host, source = resolve_robot_host(args.host)
        print(f"사용 호스트: {host} ({source})", flush=True)
    except Exception as exc:
        host = None
        host_error = f"호스트 검색 실패: {exc}"

    events = queue.Queue()
    robot_thread = None
    if "network" in selected:
        status, detail = run_network(host, args.timeout) if host else ("FAIL", host_error)
        results["network"] = (status, detail)
        print(f"[{status}] {LABELS['network']}: {detail}", flush=True)
        timed_out = "제한 시간 초과" in detail

    robot_steps = [step for step in selected if step not in ("network", "connect")]
    can_connect = host is not None and not timed_out and (args.step or results["network"][0] == "PASS")
    if can_connect and any(step != "network" for step in selected):
        robot_thread = threading.Thread(target=robot_worker,
                                        args=(events, robot_steps, host, args.timeout, args.show), daemon=True)
        robot_thread.start()
        try:
            _, connect_status, connect_detail = events.get(timeout=max(15.0, args.timeout))
        except queue.Empty:
            connect_status, connect_detail = "FAIL", f"{max(15.0, args.timeout):g}초 제한 시간 초과"
            timed_out = True
    else:
        connect_status = "FAIL" if host is None and args.step else "SKIP"
        connect_detail = host_error if host is None else "네트워크 연결 후 실행 가능"

    for step in selected:
        if step == "network":
            continue
        if step == "connect":
            status, detail = connect_status, connect_detail
        elif connect_status != "PASS":
            status = "FAIL" if args.step and connect_status == "FAIL" else "SKIP"
            detail = connect_detail if status == "FAIL" else "SDK 연결 후 실행 가능"
        elif timed_out:
            status, detail = "SKIP", "이전 단계 시간 초과로 연결 상태 불확실"
        else:
            try:
                event_step, status, detail = events.get(timeout=args.timeout)
                if event_step != step:
                    raise RuntimeError(f"예상하지 못한 단계 결과: {event_step}")
            except queue.Empty:
                status, detail = "FAIL", f"{args.timeout:g}초 제한 시간 초과"
                timed_out = True
        results[step] = (status, detail)
        print(f"[{status}] {LABELS[step]}: {detail}", flush=True)

    if robot_thread and not timed_out:
        robot_thread.join(timeout=max(3.0, min(args.timeout, 10.0)))
        if robot_thread.is_alive():
            timed_out = True
            print("경고: SDK 연결 종료 시간 초과", flush=True)

    counts = {status: sum(result[0] == status for result in results.values())
              for status in ("PASS", "FAIL", "SKIP")}
    print(f"요약: PASS {counts['PASS']} / FAIL {counts['FAIL']} / SKIP {counts['SKIP']}")
    for step, (status, _) in results.items():
        if status == "FAIL":
            print(f"다음 확인 · {LABELS[step]}: {HINTS[step]}")
    if timed_out:
        # A blocked SDK/DNS call may leave threads running. Exit after the summary.
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
