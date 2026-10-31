"""Shared names and spoken text for variable-length timer clips."""
from common import ROOT


def clip(kind: str, seconds: int = 0):
    return f"{kind}-{seconds}" if kind != "up" else "times-up"


def phrase(kind: str, seconds: int, lang: str) -> str:
    if kind == "up":
        return "시간이 다 되었습니다. 마무리해 주세요." if lang == "ko" else "Time's up. Please wrap up."
    if lang == "ko":
        length = f"{seconds // 60}분" + (f" {seconds % 60}초" if seconds % 60 else "") if seconds >= 60 else f"{seconds}초"
        return f"{length} 남았습니다." if kind == "left" else f"{length} 타이머를 시작할게요."
    length = f"{seconds // 60} minute{'s' if seconds // 60 != 1 else ''}" + (f" {seconds % 60} seconds" if seconds % 60 else "") if seconds >= 60 else f"{seconds} seconds"
    return f"{length} remaining." if kind == "left" else f"Starting a {length} timer."


def path(kind: str, seconds: int, lang: str):
    return ROOT / "audio" / "timer" / lang / (clip(kind, seconds) + ".mp3")
