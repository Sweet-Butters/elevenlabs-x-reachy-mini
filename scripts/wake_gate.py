"""Conservative name gate for committed Scribe transcripts."""
import re
import time

WAKE = re.compile(r"^(?:hey[ ,!]*|헤이\s*)?(?:리\s*치|리찌|리\s*치아|reachy|reachie|richie)(?:\s*야)?(?=$|[\s,!?，。.!?])", re.I)


def split_wake(text):
    # Only a greeting or filler may precede the name. Avoid matching names in quoted speech.
    leading = re.match(r"^\s*(?:(?:저기요?|안녕하세요|안녕|있잖아|음|hello|hi)[,!\s]+)?", text, re.I)
    start = leading.end()
    match = WAKE.match(text[start:])
    if not match:
        return None
    return text[start + match.end():].strip(" \t,，.!?。")


class WakeGate:
    def __init__(self, followup_seconds=5):
        self.followup_seconds = followup_seconds
        self.ack_until = 0.0
        self.followup_until = 0.0

    def decide(self, text, now=None):
        now = time.monotonic() if now is None else now
        remainder = split_wake(text)
        if remainder is not None:
            self.followup_until = 0.0
            if remainder:
                self.ack_until = 0.0
                return "send", remainder
            self.ack_until = now + 6.0
            return "ack", ""
        if now < self.ack_until:
            self.ack_until = 0.0
            return "send", text.strip()
        if now < self.followup_until:
            self.followup_until = 0.0
            return "send", text.strip()
        return "ignore", ""

    def answered(self, now=None):
        now = time.monotonic() if now is None else now
        self.followup_until = now + self.followup_seconds if self.followup_seconds else 0.0
