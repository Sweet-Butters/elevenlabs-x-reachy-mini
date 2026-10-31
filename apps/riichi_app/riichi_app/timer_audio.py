import re

def announcement_schedule(total):
    if total <= 0:
        raise ValueError("timer length must be positive")
    if total >= 300:
        points = [(total // 120) * 60, 60, 30]
    elif total > 60:
        points = list(range(((total - 1) // 60) * 60, 0, -60)) + [30]
    else:
        points = [30, 10]
    return sorted({p for p in points if 0 < p < total}, reverse=True) + [0]

def duration_from_text(text):
    s = text.lower()
    if not re.search(r"타이머|timer", s):
        return None
    minutes = re.search(r"(\d+)\s*(?:분|minutes?|mins?)", s)
    seconds = re.search(r"(\d+)\s*(?:초|seconds?|secs?)", s)
    value = (int(minutes.group(1)) * 60 if minutes else 0) + (int(seconds.group(1)) if seconds else 0)
    return value if 0 < value <= 3600 else None

def phrase(kind, seconds, lang):
    if kind == "up":
        return "시간이 다 되었습니다. 마무리해 주세요." if lang == "ko" else "Time's up. Please wrap up."
    if lang == "ko":
        length = f"{seconds // 60}분" + (f" {seconds % 60}초" if seconds % 60 else "") if seconds >= 60 else f"{seconds}초"
        return f"{length} 남았습니다." if kind == "left" else f"{length} 타이머를 시작할게요."
    length = f"{seconds // 60} minute{'s' if seconds // 60 != 1 else ''}" + (f" {seconds % 60} seconds" if seconds % 60 else "") if seconds >= 60 else f"{seconds} seconds"
    return f"{length} remaining." if kind == "left" else f"Starting a {length} timer."
