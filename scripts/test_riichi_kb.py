"""Fresh ElevenAgents text session for each KB acceptance question."""
import queue
import re
import sys
import time

from common import AGENT_ID, ROOT, api_key
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation, ConversationInitiationData


CASES = [
    ('주차 돼?', r'주차.{0,30}(제공하지|없|불가|안 돼)'),
    ('1등 하려면 ElevenLabs 꼭 써야 해?', r'ElevenLabs'),
    ('발표는 어떻게 해?', r'PPT'),
    ('상장은 언제 줘?', r'(현장|시상식).{0,40}(드려|받|수여)'),
    ('참가확인서 받을 수 있어?', r'참가확인서.{0,80}(PDF|받|발급)'),
    ('몇 시에 끝나?', r'(5시|다섯 시)'),
    ('참가자 전원 받는 거 있어?', r'Creator.{0,20}(1개월|한 달)'),
    ('신청 아직 돼?', r'신청.{0,25}마감|마감.{0,25}신청'),
    ('Can I use ChatGPT?', r'(?i)(yes|can use|allowed).{0,100}ChatGPT|ChatGPT.{0,100}(yes|can use|allowed)'),
    ('제출 마감 언제야?', r'(3시|세 시).{0,12}(30분|반)'),
    ('상은 몇 개야?', r'(13|열세)\s*개'),
]


def ask(client, question, english=False):
    replies = queue.Queue()
    override = {'conversation': {'text_only': True}}
    if english:
        override['agent'] = {'language': 'en'}
    config = ConversationInitiationData(conversation_config_override=override)
    conv = Conversation(client, AGENT_ID, requires_auth=True, config=config,
                        callback_agent_response=replies.put)
    conv.start_session()
    try:
        deadline = time.monotonic() + 25
        while conv._ws is None and time.monotonic() < deadline:
            if conv._thread and not conv._thread.is_alive():
                raise RuntimeError('connection closed')
            time.sleep(.1)
        if conv._ws is None:
            raise TimeoutError('connection timeout')
        try:
            replies.get(timeout=8)  # greeting
        except queue.Empty:
            pass
        while not replies.empty():
            replies.get_nowait()
        conv.send_user_message(question)
        deadline = time.monotonic() + 55
        while time.monotonic() < deadline:
            answer = replies.get(timeout=max(1, deadline - time.monotonic()))
            if not any(x in answer for x in ('확인해 볼게요', 'Let me check', '잠시만요')):
                return answer
        raise TimeoutError('only interim response')
    finally:
        conv.end_session()
        conv.wait_for_session_end()


def main():
    client = ElevenLabs(api_key=api_key())
    version = client.conversational_ai.agents.get(AGENT_ID).version_id
    lines = ['\n## KB 웹사이트·CS 갱신 후 테스트 — 2026-10-31\n',
             f'Main version: `{version}`. 이전 테스트와 같은 ElevenAgents WebSocket 텍스트 방식. 질문마다 새 세션, 영어는 `en` 프리셋.\n']
    passed = 0
    chosen = [(i, *case) for i, case in enumerate(CASES, 1) if not sys.argv[1:] or str(i) in sys.argv[1:]]
    for idx, q, expected in chosen:
        try:
            answer = ask(client, q, english=q.startswith('Can I'))
            ok = bool(re.search(expected, answer))
            if q == '상장은 언제 줘?' and any(x in answer for x in ('우편', '배송', '메일로')):
                ok = False
            if q == '신청 아직 돼?' and any(x in answer for x in ('신청 가능', '모집 중')):
                ok = False
            if q == '신청 아직 돼?' and any(x in answer for x in ('확실히 아는 내용이 아니라', '모르', '운영진에게 물어')):
                ok = False
            if q == 'Can I use ChatGPT?' and not answer.strip().isascii():
                ok = False
            passed += ok
            status = 'PASS' if ok else 'FAIL'
        except Exception as exc:
            answer = f'ERROR: {type(exc).__name__}: {exc}'
            status = 'FAIL'
        print(f'{idx}/11 {status} {q} => {answer}', flush=True)
        lines.append(f'{idx}. **Q:** {q}  \n   **A:** {answer}  \n   **Result:** {status}.\n')
    lines.append(f'**Summary:** {passed}/{len(chosen)} passed (questions {", ".join(str(x[0]) for x in chosen)}).\n')
    with (ROOT / 'agent' / 'test-results.md').open('a', encoding='utf-8') as f:
        f.write('\n'.join(lines))


if __name__ == '__main__':
    main()
