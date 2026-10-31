"""Generate the prewritten Korean announcements as MP3 files."""

import argparse
import sys

from common import AGENT_ID, AUDIO_DIR, ROOT, api_key, audio_path, lines


def choose_voice(client, requested: str | None) -> str:
    if requested:
        return requested
    try:
        agent = client.conversational_ai.agents.get(AGENT_ID)
        voice_id = agent.conversation_config.tts.voice_id
        if voice_id:
            print("에이전트에 설정된 목소리를 사용합니다.")
            return voice_id
    except Exception as exc:
        print(f"에이전트 목소리 조회 실패: {type(exc).__name__}. 사용 가능한 목소리를 찾습니다.")
    voices = client.voices.get_all().voices
    if not voices:
        raise RuntimeError("사용 가능한 목소리가 없습니다. --voice VOICE_ID를 지정해 주세요.")
    for voice in voices:
        languages = getattr(voice, "verified_languages", None) or []
        if any(getattr(item, "language", None) in {"ko", "kor"} for item in languages):
            print(f"한국어 검증 목소리 {voice.name}을 사용합니다.")
            return voice.voice_id
    print(f"다국어 모델로 {voices[0].name} 목소리를 사용합니다.")
    return voices[0].voice_id


def main() -> None:
    parser = argparse.ArgumentParser(description="리치 대본을 MP3로 생성합니다.")
    parser.add_argument("--voice", help="ElevenLabs voice ID (기본: 에이전트 설정)")
    parser.add_argument("--force", action="store_true", help="이미 있는 파일도 다시 생성")
    parser.add_argument("--welcome", action="store_true", help="체크인 환영 대사를 audio/welcome에 생성")
    args = parser.parse_args()

    from elevenlabs.client import ElevenLabs

    client = ElevenLabs(api_key=api_key())
    voice_id = choose_voice(client, args.voice)
    directory = ROOT / "audio" / "welcome" if args.welcome else AUDIO_DIR
    source = ROOT / "agent" / "welcome-lines.ko.md" if args.welcome else ROOT / "agent" / "lines.ko.md"
    print(f"voice_id: {voice_id}")
    directory.mkdir(parents=True, exist_ok=True)
    for number, name, spoken in lines(source):
        target = audio_path(number, name, directory)
        if target.is_file() and target.stat().st_size > 0 and not args.force:
            print(f"건너뜀: {target.relative_to(AUDIO_DIR.parent.parent)}")
            continue
        audio = client.text_to_speech.convert(
            text=spoken,
            voice_id=voice_id,
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )
        partial = target.with_suffix(".partial")
        try:
            with partial.open("wb") as file:
                for chunk in audio:
                    file.write(chunk)
            if partial.stat().st_size == 0:
                raise RuntimeError("빈 오디오가 반환됐습니다.")
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)
        print(f"생성: {target.relative_to(AUDIO_DIR.parent.parent)} ({target.stat().st_size:,} bytes)", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"오류: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
