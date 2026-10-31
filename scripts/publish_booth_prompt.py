"""Publish the local TripPups prompt to the separate booth agent."""

import json

from common import AGENT_ID as HACKATHON_AGENT_ID, ROOT, api_key
from elevenlabs.client import ElevenLabs


def main():
    config_path = ROOT / "apps" / "riichi_app" / "riichi_app" / "config.json"
    agent_id = json.loads(config_path.read_text(encoding="utf-8"))["agent_id"]
    if agent_id == HACKATHON_AGENT_ID:
        raise RuntimeError("App still points to the hackathon agent")
    prompt = (ROOT / "agent" / "booth" / "system-prompt.md").read_text(encoding="utf-8").strip()
    client = ElevenLabs(api_key=api_key())
    before = client.conversational_ai.agents.get(agent_id)
    client.conversational_ai.agents.update(
        agent_id, branch_id=before.main_branch_id,
        conversation_config={"agent": {"prompt": {"prompt": prompt}}},
        version_description="Make fixed booth facts explicit for short RAG answers")
    after = client.conversational_ai.agents.get(agent_id)
    assert after.conversation_config.agent.prompt.prompt.strip() == prompt
    assert after.conversation_config.agent.prompt.knowledge_base == before.conversation_config.agent.prompt.knowledge_base
    assert after.conversation_config.tts.voice_id == before.conversation_config.tts.voice_id
    print(f"Published booth agent {agent_id} version {after.version_id}")


if __name__ == "__main__":
    main()
