"""
Turn-based interview: AI asks (text + audio), user answers, then the next question is asked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from app.services.llama_client import generate_followup, generate_opening_question
from app.services.tts import synthesize_wav_base64
from app.workers.audio_worker import AudioWorker
from app.workers.pool import run_in_worker
from app.workers.whisper_client import transcribe_pcm

SAMPLE_RATE = 16000
SILENCE_CHUNKS_TO_END = 2
MAX_TURNS = 10


@dataclass
class InterviewTurnState:
    phase: str = "idle"
    turn_index: int = 0
    max_turns: int = MAX_TURNS
    current_question: str = ""
    qa_history: list[dict] = field(default_factory=list)
    answer_pcm: bytearray = field(default_factory=bytearray)
    answer_parts: list[str] = field(default_factory=list)
    silence_streak: int = 0
    had_speech: bool = False
    _audio: AudioWorker = field(default_factory=AudioWorker)


_orchestrators: dict[str, InterviewTurnState] = {}


def get_orchestrator(session_id: str) -> InterviewTurnState:
    if session_id not in _orchestrators:
        _orchestrators[session_id] = InterviewTurnState()
    return _orchestrators[session_id]


def clear_orchestrator(session_id: str) -> None:
    _orchestrators.pop(session_id, None)


def _speech_ratio(pcm: bytes, worker: AudioWorker) -> float:
    frames = worker._split_frames(pcm)
    if not frames:
        return 0.0
    return sum(1 for f in frames if worker._is_speech(f)) / len(frames)


async def start_interview_turns(
    session_id: str,
    job_title: str,
    send: Callable[[dict], Awaitable[None]],
) -> None:
    """Ask the first question after WebSocket connects."""
    from app.session_manager import get_interview_session

    sess = get_interview_session(session_id)
    language = sess.language if sess else "en"
    state = get_orchestrator(session_id)
    state.phase = "asking"
    state.turn_index = 0
    state.max_turns = (sess.question_count if sess else MAX_TURNS) or MAX_TURNS
    state.qa_history = []
    question = generate_opening_question(job_title, language=language)
    await _emit_question(session_id, state, question, send)


async def _emit_question(
    session_id: str,
    state: InterviewTurnState,
    question: str,
    send: Callable[[dict], Awaitable[None]],
) -> None:
    state.current_question = question
    state.phase = "asking"
    state.answer_pcm = bytearray()
    state.answer_parts = []
    state.silence_streak = 0
    state.had_speech = False

    from app.session_manager import get_interview_session

    sess = get_interview_session(session_id)
    voice = (sess.voice_preset if sess else None) or "Jasper"
    language = (sess.language if sess else "en")
    audio_b64, tts_engine = await run_in_worker(
        synthesize_wav_base64,
        question,
        voice,
        language,
    )
    await send({
        "type": "interview.question",
        "session_id": session_id,
        "turn_index": state.turn_index,
        "total_turns": state.max_turns,
        "text": question,
        "language": language,
        "audio_base64": audio_b64,
        "audio_format": "wav" if audio_b64 else None,
        "tts_engine": tts_engine,
        "use_browser_tts": audio_b64 is None,
    })


async def on_listen_start(session_id: str, send: Callable[[dict], Awaitable[None]]) -> None:
    from app.session_manager import get_interview_session

    state = get_orchestrator(session_id)
    sess = get_interview_session(session_id)
    is_fr = bool(sess and sess.language == "fr")
    state.phase = "listening"
    await send({
        "type": "interview.phase",
        "session_id": session_id,
        "phase": "listening",
        "message": "A vous de repondre." if is_fr else "Your turn - speak your answer.",
    })


async def on_audio_chunk(
    session_id: str,
    pcm: bytes,
    job_title: str,
    send: Callable[[dict], Awaitable[None]],
) -> None:
    """Buffer audio while listening; finalize answer after silence."""
    state = get_orchestrator(session_id)
    if state.phase != "listening":
        return

    state.answer_pcm.extend(pcm)
    ratio = _speech_ratio(pcm, state._audio)

    if ratio >= 0.12:
        state.had_speech = True
        state.silence_streak = 0
        await send({
            "type": "interview.listening",
            "session_id": session_id,
            "speaking": True,
        })
    elif state.had_speech:
        state.silence_streak += 1
        await send({
            "type": "interview.listening",
            "session_id": session_id,
            "speaking": False,
            "silence_chunks": state.silence_streak,
        })
        if state.silence_streak >= SILENCE_CHUNKS_TO_END:
            await _finalize_answer(session_id, job_title, send)


async def _finalize_answer(
    session_id: str,
    job_title: str,
    send: Callable[[dict], Awaitable[None]],
) -> None:
    from app.session_manager import get_interview_session

    state = get_orchestrator(session_id)
    if state.phase != "listening":
        return

    sess = get_interview_session(session_id)
    language = (sess.language if sess else "en")
    is_fr = language == "fr"
    state.phase = "processing"
    await send({
        "type": "interview.phase",
        "session_id": session_id,
        "phase": "processing",
        "message": "Traitement de votre reponse..." if is_fr else "Processing your answer...",
    })

    pcm = bytes(state.answer_pcm)
    asr = {}
    if len(pcm) >= SAMPLE_RATE:
        asr = await run_in_worker(transcribe_pcm, pcm, SAMPLE_RATE, language)
        answer_text = (asr.get("text") or "").strip()
    else:
        answer_text = ""

    if not answer_text and state.answer_parts:
        answer_text = " ".join(state.answer_parts).strip()

    if not answer_text or "[mock" in answer_text.lower():
        if asr_engine := (asr.get("engine") if len(pcm) >= SAMPLE_RATE else "none"):
            if asr_engine in ("none", "mock"):
                answer_text = (
                    "(Parole non reconnue. Installez faster-whisper, redemarrez le serveur, "
                    "et parlez clairement pendant au moins cinq secondes.)"
                    if is_fr else
                    "(Speech not recognized. Install faster-whisper, restart the server, "
                    "and speak clearly for at least five seconds.)"
                )
    if not answer_text:
        answer_text = (
            "(Aucune parole detectee - parlez plus fort ou plus longtemps, puis cliquez sur J'ai fini.)"
            if is_fr else
            "(No speech detected - speak louder or longer, then click I'm done speaking.)"
        )

    state.qa_history.append({
        "turn_index": state.turn_index,
        "question": state.current_question,
        "answer": answer_text,
    })

    await send({
        "type": "interview.answer",
        "session_id": session_id,
        "turn_index": state.turn_index,
        "question": state.current_question,
        "answer": answer_text,
    })

    state.turn_index += 1
    if state.turn_index >= state.max_turns:
        await send({
            "type": "interview.complete",
            "session_id": session_id,
            "turns": state.qa_history,
            "message": "Entretien termine. Cliquez sur Terminer et noter." if is_fr else "Interview complete. Click End & score.",
        })
        state.phase = "idle"
        return

    asked = [t["question"] for t in state.qa_history]
    context = " ".join(
        f"Q: {t['question']} A: {t['answer']}" for t in state.qa_history
    )
    next_q = generate_followup(
        job_title,
        answer_text,
        context,
        asked_questions=asked,
        language=language,
    )
    await _emit_question(session_id, state, next_q, send)


async def force_finalize(session_id: str, job_title: str, send: Callable) -> None:
    """Manual 'I'm done speaking' from client."""
    state = get_orchestrator(session_id)
    if state.phase == "listening":
        await _finalize_answer(session_id, job_title, send)
