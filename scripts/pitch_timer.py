"""Offline keyboard timer for the ten finals presentations (Windows)."""

import argparse
import math
import queue
import sys
import threading
import time

from common import ROOT
from play_lines import play


CLIPS = ("2-min-left", "1-min-left", "times-up")


def announcement_schedule(total_seconds: int) -> list[int]:
    """Remaining seconds at which to speak; zero is always the final cue."""
    if total_seconds <= 0:
        raise ValueError("timer length must be positive")
    if total_seconds >= 300:
        points = [(total_seconds // 120) * 60, 60, 30]
    elif total_seconds > 60:
        points = list(range(((total_seconds - 1) // 60) * 60, 0, -60)) + [30]
    else:
        points = [30, 10]
    return sorted({p for p in points if 0 < p < total_seconds}, reverse=True) + [0]
DIGITS = {
    "0": ("###", "# #", "# #", "# #", "###"),
    "1": ("  #", "  #", "  #", "  #", "  #"),
    "2": ("###", "  #", "###", "#  ", "###"),
    "3": ("###", "  #", "###", "  #", "###"),
    "4": ("# #", "# #", "###", "  #", "  #"),
    "5": ("###", "#  ", "###", "  #", "###"),
    "6": ("###", "#  ", "###", "# #", "###"),
    "7": ("###", "  #", "  #", "  #", "  #"),
    "8": ("###", "# #", "###", "# #", "###"),
    "9": ("###", "# #", "###", "  #", "###"),
    ":": ("   ", " # ", "   ", " # ", "   "),
}


def clock_text(seconds: float) -> str:
    value = max(0, math.ceil(seconds))
    return f"{value // 60:02d}:{value % 60:02d}"


def audio_worker(work: queue.Queue) -> None:
    while True:
        item = work.get()
        try:
            if item is None:
                return
            try:
                play(item)
            except Exception as exc:
                print(f"\n오디오 재생 오류 ({item.name}): {exc}", flush=True)
        finally:
            work.task_done()


def main() -> None:
    parser = argparse.ArgumentParser(description="리치 결선 발표 오프라인 타이머")
    parser.add_argument("--lang", choices=("ko", "en"), default="ko")
    parser.add_argument("--minutes", type=float, default=3.0, help="발표 길이 (분, 기본 3)")
    parser.add_argument("--announce-at", default="1,2,3", help="세 안내 시점의 경과 분 (기본 1,2,3)")
    parser.add_argument("--time-scale", type=float, default=1.0, help="테스트용 시간 배율 (예: 0.02)")
    parser.add_argument("--demo", action="store_true", help="한 발표를 자동 시작하고 종료 (검증용)")
    args = parser.parse_args()
    try:
        points = tuple(float(part.strip()) for part in args.announce_at.split(","))
    except ValueError:
        parser.error("--announce-at은 쉼표로 구분한 숫자 3개여야 합니다.")
    if (args.minutes <= 0 or args.time_scale <= 0 or len(points) != 3
            or any(not 0 < point <= args.minutes for point in points)
            or tuple(sorted(points)) != points or len(set(points)) != 3):
        parser.error("시간은 양수이고, 안내 시점 3개는 발표 길이 이내의 증가하는 값이어야 합니다.")
    for lang in ("ko", "en"):
        for clip in CLIPS:
            path = ROOT / "audio" / "timer" / lang / f"{clip}.mp3"
            if not path.is_file() or path.stat().st_size == 0:
                parser.error(f"MP3가 없습니다: {path}. make_timer_lines.py를 먼저 실행하세요.")

    if not args.demo and sys.platform != "win32":
        parser.error("키보드 조작은 Windows 콘솔에서 실행해야 합니다.")
    if not args.demo:
        import msvcrt

    work: queue.Queue = queue.Queue()
    thread = threading.Thread(target=audio_worker, args=(work,), daemon=True)
    thread.start()

    number = 1
    next_lang = args.lang
    current_lang = args.lang
    state = "ready"
    elapsed = 0.0  # 발표 시간 기준 초
    resumed_at = 0.0
    fired = 0
    last_display = ""

    def show(force: bool = False, display_elapsed: float | None = None) -> None:
        nonlocal last_display
        remaining = args.minutes * 60 - (elapsed if display_elapsed is None else display_elapsed)
        label = f"발표 {number:02d}/10 [{current_lang.upper() if state != 'ready' else next_lang.upper()}] {clock_text(remaining)}  {state}"
        if force or label != last_display:
            if sys.stdout.isatty():
                digits = clock_text(remaining)
                art = "\n".join("  ".join(DIGITS[char][row] for char in digits) for row in range(5))
                print(f"\x1b[2J\x1b[H발표 {number:02d}/10  [{current_lang.upper() if state != 'ready' else next_lang.upper()}]  {state}\n\n{art}\n\n{digits}\n\nEnter/Space 시작 · p 일시정지 · r 초기화 · k/e 언어 · q 종료", flush=True)
            else:
                print(label, flush=True)
            last_display = label

    def start() -> None:
        nonlocal state, elapsed, resumed_at, fired, current_lang
        if state == "done":
            return
        current_lang = next_lang
        state = "running"
        elapsed = 0.0
        fired = 0
        resumed_at = time.monotonic()
        print(f"\n발표 {number:02d} 시작 ({current_lang.upper()})", flush=True)
        show(True)

    print("Enter/Space 시작 · p 일시정지/재개 · r 현재 발표 초기화 · k/e 다음 발표 언어 · q 종료", flush=True)
    if args.demo:
        start()
    else:
        show(True)

    try:
        while True:
            now = time.monotonic()
            if state == "running":
                current_elapsed = elapsed + (now - resumed_at) / args.time_scale
                while fired < 3 and current_elapsed >= points[fired] * 60:
                    clip = CLIPS[fired]
                    path = ROOT / "audio" / "timer" / current_lang / f"{clip}.mp3"
                    print(f"\n발표 {number:02d} {clock_text(points[fired] * 60)} 경과: {clip} ({current_lang.upper()})", flush=True)
                    work.put(path)
                    fired += 1
                if current_elapsed >= args.minutes * 60:
                    elapsed = args.minutes * 60
                    state = "done"
                    print(f"\n발표 {number:02d} 종료", flush=True)
                    show(True)
                else:
                    show(display_elapsed=current_elapsed)
            if args.demo and state == "done":
                break
            if not args.demo and msvcrt.kbhit():
                key = msvcrt.getwch().lower()
                if key == "q":
                    break
                if key in ("\r", " "):
                    if state == "done":
                        if number == 10:
                            print("\n10명 발표가 모두 끝났습니다.", flush=True)
                        else:
                            number += 1
                            state = "ready"
                            elapsed = 0.0
                            start()
                    elif state == "ready":
                        start()
                elif key == "p" and state in ("running", "paused"):
                    if state == "running":
                        elapsed += (now - resumed_at) / args.time_scale
                        state = "paused"
                    else:
                        resumed_at = now
                        state = "running"
                    print(f"\n발표 {number:02d} {state}", flush=True)
                    show(True)
                elif key == "r":
                    elapsed = 0.0
                    fired = 0
                    state = "ready"
                    print(f"\n발표 {number:02d} 초기화. Enter/Space로 다시 시작", flush=True)
                    show(True)
                elif key in ("k", "e"):
                    next_lang = "ko" if key == "k" else "en"
                    print(f"\n다음 시작 언어: {next_lang.upper()}", flush=True)
                    show(True)
            time.sleep(0.04)
    except KeyboardInterrupt:
        pass
    finally:
        if args.demo:
            work.join()
        print("\n타이머 종료", flush=True)


if __name__ == "__main__":
    main()
