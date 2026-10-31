import os
from pathlib import Path

KEY_FILE = Path.home() / ".elevenlabs" / "reachy.env"

def api_key():
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if key:
        return key
    if KEY_FILE.is_file():
        for line in KEY_FILE.read_text(encoding="utf-8-sig").splitlines():
            if line.startswith("ELEVENLABS_API_KEY="):
                return line.partition("=")[2].strip().strip('"').strip("'")
    raise RuntimeError("ElevenLabs API 키가 없습니다. 설정에서 저장해 주세요.")

def save_api_key(key):
    key = key.strip()
    if not key or any(c in key for c in "\r\n\x00"):
        raise ValueError("올바른 API 키를 입력해 주세요.")
    KEY_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        out.write("ELEVENLABS_API_KEY=" + key + "\n")
    try:
        os.chmod(KEY_FILE, 0o600)
    except OSError:
        pass
