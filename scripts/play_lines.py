"""Play a cached MP3 through Windows' built-in MCI player, offline."""

import argparse
import ctypes
import sys

from common import audio_path, lines


def play(path) -> None:
    if sys.platform != "win32":
        raise RuntimeError("이 재생기는 Windows용입니다.")
    mci = ctypes.windll.winmm.mciSendStringW
    error_text = ctypes.windll.winmm.mciGetErrorStringW

    def command(value: str) -> None:
        code = mci(value, None, 0, None)
        if code:
            buffer = ctypes.create_unicode_buffer(256)
            error_text(code, buffer, len(buffer))
            raise RuntimeError(f"오디오 재생 실패: {buffer.value}")

    command(f'open "{path}" type mpegvideo alias reachy_line')
    try:
        command("play reachy_line wait")
    finally:
        command("close reachy_line")


def main() -> None:
    parser = argparse.ArgumentParser(description="저장된 리치 대사를 오프라인으로 재생합니다.")
    parser.add_argument("number", type=int, nargs="?", help="재생할 대사 번호")
    parser.add_argument("--list", action="store_true", help="대사와 MP3 준비 상태 보기")
    args = parser.parse_args()
    entries = lines()
    if args.list or args.number is None:
        for number, name, spoken in entries:
            path = audio_path(number, name)
            status = f"{path.stat().st_size:,} bytes" if path.is_file() else "미생성"
            print(f"{number:2d}. {name} [{status}] {spoken}")
        return
    match = next(((name, spoken) for number, name, spoken in entries if number == args.number), None)
    if match is None:
        parser.error("대사 번호를 찾을 수 없습니다. --list로 확인해 주세요.")
    path = audio_path(args.number, match[0])
    if not path.is_file():
        parser.error("MP3가 없습니다. 먼저 make_lines.py를 실행해 주세요.")
    print(f"재생: {args.number}. {match[1]}")
    play(path)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"오류: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
