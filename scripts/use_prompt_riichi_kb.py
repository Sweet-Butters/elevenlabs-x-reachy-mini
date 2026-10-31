"""Keep the single indexed KB in context for short factual participant questions."""
from common import AGENT_ID, api_key
from elevenlabs.client import ElevenLabs

c = ElevenLabs(api_key=api_key())
before = c.conversational_ai.agents.get(AGENT_ID)
p = before.conversation_config.agent.prompt
assert len(p.knowledge_base) == 1
ref = p.knowledge_base[0]
assert 'prompt' in c.conversational_ai.knowledge_base.documents.get(ref.id).supported_usages
c.conversational_ai.agents.update(
    AGENT_ID, branch_id=before.main_branch_id,
    conversation_config={'agent': {'prompt': {'knowledge_base': [
        {'type': ref.type, 'name': ref.name, 'id': ref.id, 'usage_mode': 'prompt'}]}}},
    version_description='Keep current hackathon KB in context for reliable short answers')
after = c.conversational_ai.agents.get(AGENT_ID, branch_id=before.main_branch_id)
assert len(after.conversation_config.agent.prompt.knowledge_base) == 1
assert after.conversation_config.agent.prompt.knowledge_base[0].usage_mode == 'prompt'
assert after.conversation_config.agent.prompt.prompt == p.prompt
assert after.conversation_config.agent.prompt.tools == p.tools
assert after.conversation_config.tts.voice_id == before.conversation_config.tts.voice_id
b = next(x for x in c.conversational_ai.agents.branches.list(AGENT_ID).results if x.id == before.main_branch_id)
assert b.current_live_percentage == 100 and not b.draft_exists
print(after.version_id, ref.id, 'prompt mode', b.current_live_percentage, 'no draft')
