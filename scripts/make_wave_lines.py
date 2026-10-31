"""Create cached acknowledgement and wave greetings in Sena's voice."""
from common import ROOT, api_key
from elevenlabs.client import ElevenLabs

LINES = {"ack": "네!", "01": "네, 저도 반가워요! 안녕하세요!", "02": "안녕하세요! 만나서 정말 반가워요!"}


def main():
    directory = ROOT / "audio" / "wave"
    directory.mkdir(parents=True, exist_ok=True)
    client = ElevenLabs(api_key=api_key())
    for name, line in LINES.items():
        target = directory / f"{name}.mp3"
        if target.is_file() and target.stat().st_size:
            print(f"건너뜀: {target.name}")
            continue
        audio = client.text_to_speech.convert(text=line, voice_id="vJ170fCwESgE1tjW39So",
                                              model_id="eleven_multilingual_v2", output_format="mp3_44100_128")
        partial = target.with_suffix(".partial")
        try:
            with partial.open("wb") as out:
                for chunk in audio:
                    out.write(chunk)
            if not partial.stat().st_size:
                raise RuntimeError("빈 오디오")
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)
        print(f"생성: {target.name} ({target.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
