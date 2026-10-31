"""Small shared helpers for the hackathon fallback scripts."""

import os
from pathlib import Path

AGENT_ID = "agent_9101m65rk0eqe2ytcq56ceg7hw10"
ROOT = Path(__file__).resolve().parents[1]
LINES_FILE = ROOT / "agent" / "lines.ko.md"
AUDIO_DIR = ROOT / "audio" / "lines"
KEY_FILE = Path(r"C:\Users\정회광\.elevenlabs\reachy.env")


def api_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if key:
        return key
    if KEY_FILE.is_file():
        for line in KEY_FILE.read_text(encoding="utf-8-sig").splitlines():
            if line.startswith("ELEVENLABS_API_KEY="):
                return line.partition("=")[2].strip().strip('"').strip("'")
    raise RuntimeError("ELEVENLABS_API_KEY 환경 변수 또는 reachy.env 파일이 필요합니다.")


def lines(source: Path = LINES_FILE) -> list[tuple[int, str, str]]:
    result = []
    for raw in source.read_text(encoding="utf-8").splitlines():
        if not raw.startswith("| ") or raw.startswith("| 번호") or raw.startswith("|---"):
            continue
        cells = [cell.strip() for cell in raw.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[0].isdigit():
            result.append((int(cells[0]), cells[1], cells[2]))
    if not result or len({n for n, _, _ in result}) != len(result):
        raise ValueError("대본 표를 읽을 수 없거나 번호가 중복되었습니다.")
    return result


def audio_path(number: int, name: str, directory: Path = AUDIO_DIR) -> Path:
    return directory / f"{number:02d}-{name}.mp3"
