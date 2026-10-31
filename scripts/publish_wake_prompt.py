"""Publish only the synchronized prompt; assert voice, KB and tools remain intact."""
from common import ROOT, AGENT_ID, api_key
from elevenlabs.client import ElevenLabs


def main():
    client = ElevenLabs(api_key=api_key())
    before = client.conversational_ai.agents.get(AGENT_ID)
    prompt = (ROOT / "agent" / "system-prompt.md").read_text(encoding="utf-8").strip()
    client.conversational_ai.agents.update(
        AGENT_ID, branch_id=before.main_branch_id,
        conversation_config={"agent": {"prompt": {"prompt": prompt}}},
        version_description="Riichi background conversation backstop")
    after = client.conversational_ai.agents.get(AGENT_ID, branch_id=before.main_branch_id)
    assert after.conversation_config.agent.prompt.prompt.strip() == prompt
    assert after.conversation_config.agent.prompt.knowledge_base == before.conversation_config.agent.prompt.knowledge_base
    assert after.conversation_config.agent.prompt.tools == before.conversation_config.agent.prompt.tools
    assert after.conversation_config.tts.voice_id == before.conversation_config.tts.voice_id
    print("Prompt published; KB, tools, voice unchanged.")


if __name__ == "__main__":
    main()
