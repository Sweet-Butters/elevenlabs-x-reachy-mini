"""Laptop microphone/speaker chat, or terminal-only chat, with Reachy."""

import argparse
import queue
import sys
import time

from common import AGENT_ID, api_key


def main() -> None:
    parser = argparse.ArgumentParser(description="리치와 대화합니다. Ctrl+C 또는 /quit으로 종료합니다.")
    parser.add_argument("--text", action="store_true", help="마이크와 스피커 없이 문자로 대화")
    args = parser.parse_args()

    from elevenlabs.client import ElevenLabs
    from elevenlabs.conversational_ai.conversation import Conversation, ConversationInitiationData

    key = api_key()
    client = ElevenLabs(api_key=key)
    if args.text:
        responses: queue.Queue[str] = queue.Queue()

        def on_response(response: str) -> None:
            responses.put(response)

        config = ConversationInitiationData(
            conversation_config_override={"conversation": {"text_only": True}}
        )
        conversation = Conversation(
            client, AGENT_ID, requires_auth=True, config=config,
            callback_agent_response=on_response,
        )
        conversation.start_session()
        deadline = time.monotonic() + 20
        while conversation._ws is None and time.monotonic() < deadline:
            if conversation._thread and not conversation._thread.is_alive():
                raise RuntimeError("대화 연결에 실패했습니다. 에이전트 설정과 네트워크를 확인해 주세요.")
            time.sleep(0.1)
        if conversation._ws is None:
            raise RuntimeError("대화 연결 시간이 초과됐습니다.")
        print("리치 문자 대화가 연결됐습니다. 종료: /quit", flush=True)
        try:
            greeting = responses.get(timeout=10)
            print(f"리치> {greeting}", flush=True)
        except queue.Empty:
            pass
        try:
            while True:
                try:
                    question = input("나> ").strip()
                except EOFError:
                    break
                if question.lower() in {"/quit", "/exit", "quit", "exit"}:
                    break
                if not question:
                    continue
                # A greeting can arrive before the first user turn.
                while not responses.empty():
                    responses.get_nowait()
                conversation.send_user_message(question)
                try:
                    print(f"리치> {responses.get(timeout=45)}", flush=True)
                except queue.Empty:
                    print("리치> 응답 시간 초과. 연결 상태를 확인해 주세요.", flush=True)
        finally:
            conversation.end_session()
            conversation.wait_for_session_end()
    else:
        from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface

        conversation = Conversation(
            client, AGENT_ID, requires_auth=True,
            audio_interface=DefaultAudioInterface(),
            callback_agent_response=lambda response: print(f"리치> {response}", flush=True),
            callback_user_transcript=lambda transcript: print(f"나> {transcript}", flush=True),
        )
        conversation.start_session()
        print("리치 음성 대화가 연결됐습니다. 마이크에 말하세요. 종료: Ctrl+C", flush=True)
        try:
            conversation.wait_for_session_end()
        except KeyboardInterrupt:
            conversation.end_session()
            conversation.wait_for_session_end()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"오류: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
