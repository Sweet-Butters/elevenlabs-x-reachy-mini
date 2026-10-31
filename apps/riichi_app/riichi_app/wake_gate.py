"""Conservative name gate for committed Scribe transcripts."""
import re
import time

WAKE = re.compile(r"^(?:hey[ ,!.]*|헤이[\s,!.]*)?(?:리\s*치|리찌|리\s*치아|리취|빌리지|빌리치|리지|니치|reachy|reachie|richie|ritchie|richi)(?:\s*야)?(?=$|[\s,!?，。.!?])", re.I)


NAME_ANYWHERE = re.compile(r"(?:^|[\s,!?.])((?:hey[ ,!.]*|헤이[\s,!.]*)?(?:리\s*치|리찌|리취|빌리지|빌리치|reachy|reachie|richie|ritchie)(?:\s*(?:야|아))?)(?=$|[\s,!?，。.!?])", re.I)


def split_wake(text):
    # Only a greeting or filler may precede the name. Avoid matching names in quoted speech.
    leading = re.match(r"^\s*(?:(?:저기요?|안녕하세요|안녕|있잖아|음|어|아|hello|hi)[,!.\s]+)?", text, re.I)
    start = leading.end()
    match = WAKE.match(text[start:])
    if match:
        return text[start + match.end():].strip(" \t,，.!?。")
    # 현장에서는 이름 앞에 다른 말이 섞여 받아써지는 경우가 많아, 문장 안 어디든 이름이 있으면 부른 것으로 본다
    match = NAME_ANYWHERE.search(text)
    if not match:
        return None
    rest = (text[:match.start(1)] + " " + text[match.end(1):]).strip(" \t,，.!?。")
    return rest


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
