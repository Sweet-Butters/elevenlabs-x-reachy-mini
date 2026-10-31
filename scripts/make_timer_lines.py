"""Generate six offline finals timer clips using the agent's configured voice."""

import argparse
import sys

from common import AGENT_ID, ROOT, api_key
from timer_audio import path, phrase


LINES = {
    "ko": (
        ("2-min-left", "2분 남았습니다."),
        ("1-min-left", "1분 남았습니다."),
        ("times-up", "3분이 다 되었습니다. 마무리해 주세요."),
    ),
    "en": (
        ("2-min-left", "Two minutes remaining."),
        ("1-min-left", "One minute remaining."),
        ("times-up", "Time's up. Please wrap up."),
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="리치 발표 타이머 MP3 6개 생성")
    parser.add_argument("--force", action="store_true", help="기존 MP3도 다시 생성")
    args = parser.parse_args()

    from elevenlabs.client import ElevenLabs

    client = ElevenLabs(api_key=api_key())
    agent = client.conversational_ai.agents.get(AGENT_ID)
    voice_id = agent.conversation_config.tts.voice_id
    if not voice_id:
        raise RuntimeError("에이전트에 voice_id가 설정되지 않았습니다.")
    print(f"agent: {AGENT_ID}; voice_id: {voice_id}", flush=True)

    for lang, entries in LINES.items():
        directory = ROOT / "audio" / "timer" / lang
        directory.mkdir(parents=True, exist_ok=True)
        for name, spoken in entries:
            target = directory / f"{name}.mp3"
            if target.is_file() and target.stat().st_size > 0 and not args.force:
                print(f"건너뜀: {target.relative_to(ROOT)}", flush=True)
                continue
            partial = target.with_suffix(".partial")
            try:
                audio = client.text_to_speech.convert(
                    text=spoken,
                    voice_id=voice_id,
                    model_id="eleven_multilingual_v2",
                    output_format="mp3_44100_128",
                )
                with partial.open("wb") as file:
                    for chunk in audio:
                        file.write(chunk)
                if partial.stat().st_size == 0:
                    raise RuntimeError(f"빈 오디오: {target}")
                partial.replace(target)
            finally:
                partial.unlink(missing_ok=True)
            print(f"생성: {target.relative_to(ROOT)} ({target.stat().st_size:,} bytes)", flush=True)

    # All possible minute warnings (up to 60-minute presentations), common
    # second warnings, and start confirmations for whole-minute lengths.
    clips = [("left", n * 60) for n in range(1, 31)]
    clips += [("left", n) for n in (10, 30)]
    clips += [("start", n * 60) for n in range(1, 61)]
    clips += [("start", n) for n in (10, 30, 90)]
    clips += [("up", 0)]
    for lang in ("ko", "en"):
        for kind, seconds in clips:
            target = path(kind, seconds, lang)
            if target.is_file() and target.stat().st_size and not args.force:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_suffix(".partial")
            try:
                audio = client.text_to_speech.convert(
                    text=phrase(kind, seconds, lang), voice_id=voice_id,
                    model_id="eleven_multilingual_v2", output_format="mp3_44100_128")
                with partial.open("wb") as file:
                    for chunk in audio:
                        file.write(chunk)
                if not partial.stat().st_size:
                    raise RuntimeError(f"빈 오디오: {target}")
                partial.replace(target)
            finally:
                partial.unlink(missing_ok=True)
            print(f"생성: {target.relative_to(ROOT)}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"오류: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
