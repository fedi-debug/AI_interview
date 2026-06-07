"""Turn-based interview orchestrator tests."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.environ["MOCK_LLM"] = "true"
os.environ["MOCK_ASR"] = "true"

from app.services.interview_orchestrator import (
    get_orchestrator,
    clear_orchestrator,
    start_interview_turns,
    on_listen_start,
    on_audio_chunk,
    force_finalize,
)


@pytest.mark.asyncio
async def test_interview_turn_flow():
    sent = []

    async def send(ev):
        sent.append(ev)

    sid = "test-orch-1"
    clear_orchestrator(sid)
    await start_interview_turns(sid, "Software Engineer", send)
    assert any(e["type"] == "interview.question" for e in sent)

    await on_listen_start(sid, send)
    state = get_orchestrator(sid)
    assert state.phase == "listening"

    # Simulate speech then silence via force finalize
    import numpy as np
    pcm = (np.sin(np.linspace(0, 100, 32000)) * 0.4 * 32767).astype(np.int16).tobytes()
    state.answer_pcm.extend(pcm)
    state.had_speech = True
    await force_finalize(sid, "Software Engineer", send)

    assert any(e["type"] == "interview.answer" for e in sent)
    answer_ev = [e for e in sent if e["type"] == "interview.answer"][0]
    assert "answer" in answer_ev
    clear_orchestrator(sid)
