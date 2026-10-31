"""Publish the local mode prompt and client tool, then check live main."""
from common import AGENT_ID, ROOT, api_key
from elevenlabs.client import ElevenLabs


def main():
    client = ElevenLabs(api_key=api_key())
    before = client.conversational_ai.agents.get(AGENT_ID)
    prompt = (ROOT / "agent" / "system-prompt.md").read_text(encoding="utf-8").strip()
    old = before.conversation_config.agent.prompt
    tools = [t.model_dump(exclude_none=True) for t in old.tools if t.name != "set_mode"]
    tools.append({
        "type": "client", "name": "set_mode",
        "description": "Switch Reachy to timer or welcome mode when the host explicitly requests it. Convert a spoken duration to seconds.",
        "expects_response": False, "pre_tool_speech": "force",
        "parameters": {"type": "object", "required": ["mode"], "properties": {
            "mode": {"type": "string", "enum": ["timer", "welcome"], "description": "Mode requested by the host"},
            "duration_seconds": {"type": "integer", "description": "Optional requested timer length in seconds, from 1 to 3600"}
        }}
    })
    updated = client.conversational_ai.agents.update(
        AGENT_ID, branch_id=before.main_branch_id,
        conversation_config={"agent": {"prompt": {"prompt": prompt, "tools": tools}}},
        version_description="Riichi voice mode switching with set_mode client tool")
    after = client.conversational_ai.agents.get(AGENT_ID, branch_id=before.main_branch_id)
    assert after.conversation_config.agent.prompt.prompt.strip() == prompt
    assert any(t.name == "set_mode" and t.type == "client" for t in after.conversation_config.agent.prompt.tools)
    assert after.conversation_config.tts.voice_id == before.conversation_config.tts.voice_id
    assert after.conversation_config.agent.prompt.knowledge_base == old.knowledge_base
    assert after.version_id != before.version_id
    print(f"main version: {after.version_id}; set_mode client tool: yes; prompt: match; voice and KB: unchanged")


if __name__ == "__main__":
    main()
