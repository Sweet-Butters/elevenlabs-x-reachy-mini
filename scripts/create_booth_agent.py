"""Create a separate TripPups booth agent from the existing Reachy configuration."""

import json
import time

from common import AGENT_ID as HACKATHON_AGENT_ID, ROOT, api_key
from elevenlabs.client import ElevenLabs


CONFIG = ROOT / "apps" / "riichi_app" / "riichi_app" / "config.json"
BOOTH = ROOT / "agent" / "booth"
FIRST_MESSAGE = (
    "Hi! I'm Reachy. Want to smell a forest? Pick a scent for your postcard! "
    "안녕하세요, 리치예요. 숲 향을 맡아 보세요!"
)
KOREAN_FIRST_MESSAGE = "안녕하세요, 리치예요! 숲 향을 맡아 보고 엽서에 담을 향을 골라 보세요!"


def main():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if config["agent_id"] != HACKATHON_AGENT_ID:
        raise RuntimeError("App already points to a different agent; refusing to create another")

    client = ElevenLabs(api_key=api_key())
    source = client.conversational_ai.agents.get(HACKATHON_AGENT_ID)
    assert source.conversation_config.tts.voice_id == "vJ170fCwESgE1tjW39So"
    assert any(t.name == "set_mode" and t.type == "client"
               for t in source.conversation_config.agent.prompt.tools)
    kb_text = (BOOTH / "knowledge-base.md").read_text(encoding="utf-8").strip()
    system_prompt = (BOOTH / "system-prompt.md").read_text(encoding="utf-8").strip()

    doc = client.conversational_ai.knowledge_base.documents.create_from_text(
        text=kb_text, name="TripPups booth facts (2026-11-01)")
    index = client.conversational_ai.knowledge_base.document.compute_rag_index(
        doc.id, model=source.conversation_config.agent.prompt.rag.embedding_model)
    deadline = time.monotonic() + 300
    while index.status.lower() not in ("succeeded", "failed", "error") and time.monotonic() < deadline:
        time.sleep(5)
        index = client.conversational_ai.knowledge_base.document.compute_rag_index(
            doc.id, model=source.conversation_config.agent.prompt.rag.embedding_model)
    if index.status.lower() != "succeeded":
        raise RuntimeError(f"Booth KB indexing did not succeed: {index.status}")

    duplicate = client.conversational_ai.agents.duplicate(
        agent_id=HACKATHON_AGENT_ID, name="TripPups Halloween booth — Reachy (2026-11-01)")
    agent_id = duplicate.agent_id
    print(f"Created separate agent: {agent_id}", flush=True)
    fresh = client.conversational_ai.agents.get(agent_id)
    client.conversational_ai.agents.update(
        agent_id, branch_id=fresh.main_branch_id,
        conversation_config={
            "agent": {
                "language": "en",
                "first_message": FIRST_MESSAGE,
                "prompt": {
                    "prompt": system_prompt,
                    "knowledge_base": [{"type": "text", "name": doc.name, "id": doc.id,
                                        "usage_mode": "auto"}],
                },
            },
            "language_presets": {
                "ko": {"overrides": {"agent": {"first_message": KOREAN_FIRST_MESSAGE}}},
            },
        },
        version_description="TripPups booth prompt, indexed KB, English-first greeting")
    published = client.conversational_ai.agents.get(agent_id)
    prompt = published.conversation_config.agent.prompt
    assert published.conversation_config.agent.language == "en"
    assert published.conversation_config.agent.first_message == FIRST_MESSAGE
    assert prompt.prompt.strip() == system_prompt
    assert len(prompt.knowledge_base) == 1 and prompt.knowledge_base[0].id == doc.id
    assert prompt.knowledge_base[0].usage_mode == "auto" and prompt.rag.enabled
    assert any(t.name == "set_mode" and t.type == "client" for t in prompt.tools)
    assert published.conversation_config.tts.voice_id == source.conversation_config.tts.voice_id
    assert client.conversational_ai.knowledge_base.documents.get_content(doc.id).strip() == kb_text
    assert client.conversational_ai.agents.get(HACKATHON_AGENT_ID).version_id == source.version_id
    config["agent_id"] = agent_id
    CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Published version: {published.version_id}; KB: {doc.id}; index: {index.status}; app configured", flush=True)


if __name__ == "__main__":
    main()
