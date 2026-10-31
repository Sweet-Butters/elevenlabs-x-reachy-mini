"""Ensure the KB has the index model used by the live agent."""
import time
from common import AGENT_ID, api_key
from elevenlabs.client import ElevenLabs

c = ElevenLabs(api_key=api_key())
a = c.conversational_ai.agents.get(AGENT_ID)
d = a.conversation_config.agent.prompt.knowledge_base[0].id
m = a.conversation_config.agent.prompt.rag.embedding_model
deadline = time.monotonic() + 300
while True:
    x = c.conversational_ai.knowledge_base.document.compute_rag_index(d, model=m)
    print(m, x.status, x.progress_percentage, flush=True)
    if x.status == 'succeeded':
        break
    if x.status in ('failed', 'rag_limit_exceeded', 'document_too_small') or time.monotonic() >= deadline:
        raise RuntimeError(f'Index incomplete: {x.status}')
    time.sleep(5)
