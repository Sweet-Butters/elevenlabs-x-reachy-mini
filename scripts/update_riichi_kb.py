"""Replace Riichi's single KB document, index it, and publish Main."""
import time

from common import AGENT_ID, ROOT, api_key
from elevenlabs.client import ElevenLabs


def main():
    client = ElevenLabs(api_key=api_key())
    before = client.conversational_ai.agents.get(AGENT_ID)
    old_prompt = before.conversation_config.agent.prompt
    assert len(old_prompt.knowledge_base) == 1
    old_doc = old_prompt.knowledge_base[0]
    old_voice = before.conversation_config.tts.voice_id
    old_tools = old_prompt.tools
    old_system = old_prompt.prompt
    kb_text = (ROOT / 'agent' / 'knowledge-base.md').read_text(encoding='utf-8')
    assert '010-' not in kb_text and '$897' not in kb_text and '우편' not in kb_text
    created = client.conversational_ai.knowledge_base.documents.create_from_text(
        text=kb_text, name='Hello World AI 해커톤 안내 (2026-10-31)')
    print('created', created.id)
    rag_model = old_prompt.rag.embedding_model
    index = client.conversational_ai.knowledge_base.document.compute_rag_index(
        created.id, model=rag_model)
    deadline = time.monotonic() + 300
    while index.status != 'succeeded' and time.monotonic() < deadline:
        print('index', index.status, index.progress_percentage)
        if index.status in ('failed', 'error'):
            raise RuntimeError('index failed')
        time.sleep(5)
        index = client.conversational_ai.knowledge_base.document.compute_rag_index(
            created.id, model=rag_model)
    assert index.status == 'succeeded', f'index incomplete: {index.status}'
    print('index', index.status, index.progress_percentage)
    new_ref = {'type': 'text', 'name': created.name, 'id': created.id, 'usage_mode': 'prompt'}
    client.conversational_ai.agents.update(
        AGENT_ID, branch_id=before.main_branch_id,
        conversation_config={'agent': {'prompt': {'knowledge_base': [new_ref]}}},
        version_description='Refresh Hello World AI hackathon KB from current website and operator answers')
    after = client.conversational_ai.agents.get(AGENT_ID, branch_id=before.main_branch_id)
    assert [(x.id, x.name) for x in after.conversation_config.agent.prompt.knowledge_base] == [(created.id, created.name)]
    assert after.conversation_config.tts.voice_id == old_voice
    assert after.conversation_config.agent.prompt.prompt == old_system
    assert after.conversation_config.agent.prompt.tools == old_tools
    assert after.version_id != before.version_id
    branches = client.conversational_ai.agents.branches.list(AGENT_ID).results
    main = next(x for x in branches if x.id == before.main_branch_id)
    assert main.current_live_percentage == 100, main.current_live_percentage
    assert not main.draft_exists, 'Main draft remains'
    client.conversational_ai.knowledge_base.documents.delete(old_doc.id)
    doc = client.conversational_ai.knowledge_base.documents.get(created.id, agent_id=AGENT_ID)
    assert doc.type == 'text' and doc.id == created.id
    assert client.conversational_ai.knowledge_base.documents.get_content(created.id).strip() == kb_text.strip()
    final = client.conversational_ai.agents.get(AGENT_ID, branch_id=before.main_branch_id)
    assert len(final.conversation_config.agent.prompt.knowledge_base) == 1
    print('published version', final.version_id, 'KB', created.id, 'indexed', index.status, 'live', main.current_live_percentage, 'draft', main.draft_exists)


if __name__ == '__main__':
    main()
