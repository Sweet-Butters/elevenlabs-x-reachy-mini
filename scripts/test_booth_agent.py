"""Run the five requested text-only TripPups booth conversations."""

import json
import queue
import re
import time

from common import ROOT, api_key
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation, ConversationInitiationData


CONFIG = ROOT / "apps" / "riichi_app" / "riichi_app" / "config.json"
RESULTS = ROOT / "agent" / "booth" / "test-results.md"
CASES = [
    ("How much is the Mellie Labs perfume?", "en", r"(?i)(5,?000|five thousand).*(won|원)"),
    ("What is a scent postcard?", "en", r"(?i)(postcard|card).*(hinoki|pine|moss|scent)|(?:hinoki|pine|moss|scent).*(postcard|card)"),
    ("Is the food festival today?", "en", r"(?i)(friday|saturday|fri|sat).*(over|ended|not|only|probably|likely)|(?:over|ended|not|probably|likely).*(friday|saturday|fri|sat)"),
    ("리치야, 어떤 향을 맡아 볼 수 있어?", "ko", r"(편백|소나무|이끼)"),
    ("How much is a scent postcard?", "en", r"(?i)(ask|check|confirm).*(team|table)"),
]


def ask(client, agent_id, question, language):
    replies = queue.Queue()
    config = ConversationInitiationData(conversation_config_override={
        "conversation": {"text_only": True}, "agent": {"language": language}})
    conv = Conversation(client, agent_id, requires_auth=True, config=config,
                        callback_agent_response=replies.put)
    conv.start_session()
    try:
        deadline = time.monotonic() + 25
        while conv._ws is None and time.monotonic() < deadline:
            if conv._thread and not conv._thread.is_alive():
                raise RuntimeError("connection closed")
            time.sleep(0.1)
        if conv._ws is None:
            raise TimeoutError("connection timeout")
        try:
            greeting = replies.get(timeout=12)
        except queue.Empty:
            greeting = "(no greeting received)"
        while not replies.empty():
            greeting = replies.get_nowait()
        conv.send_user_message(question)
        deadline = time.monotonic() + 55
        answer = replies.get(timeout=55)
        while re.search(r"(?i)^(let me (check|look)|i.?ll (check|look)|확인해 볼게요|잠시만요)", answer):
            answer = replies.get(timeout=max(1, deadline - time.monotonic()))
        return greeting, answer
    finally:
        conv.end_session()
        conv.wait_for_session_end()


def main():
    agent_id = json.loads(CONFIG.read_text(encoding="utf-8"))["agent_id"]
    client = ElevenLabs(api_key=api_key())
    version = client.conversational_ai.agents.get(agent_id).version_id
    lines = ["# TripPups booth agent — live text-only conversations",
             "", f"Agent: `{agent_id}`  ", f"Main version: `{version}`  ",
             "Method: ElevenAgents authenticated WebSocket, text-only override; one fresh session per question. English sessions use `en`, Korean uses `ko`.", ""]
    passed = 0
    for i, (question, language, expected) in enumerate(CASES, 1):
        try:
            greeting, answer = ask(client, agent_id, question, language)
            ok = bool(re.search(expected, answer))
            if i == 3 and re.search(r"(?i)(yes|happening|running)\b.{0,30}\b(today|now)", answer):
                ok = False
            if i == 5 and re.search(r"\b\d[\d,]*\s*(?:won|원)\b", answer, re.I):
                ok = False
            status = "PASS" if ok else "FAIL"
            passed += ok
        except Exception as exc:
            greeting, answer, status = "(session failed)", f"ERROR: {type(exc).__name__}: {exc}", "FAIL"
        print(f"{i}/5 {status}: {question} => {answer}", flush=True)
        lines += [f"## {i}. {question}", "", f"Greeting: {greeting}  ",
                  f"Visitor: {question}  ", f"Reachy: {answer}  ", f"Result: {status}", ""]
    lines += [f"Summary: {passed}/5 passed.", ""]
    RESULTS.write_text("\n".join(lines), encoding="utf-8")
    if passed != 5:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
