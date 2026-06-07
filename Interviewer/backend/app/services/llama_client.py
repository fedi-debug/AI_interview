"""llama.cpp subprocess client with varied mock interview questions."""

import json
import re
import subprocess
from typing import Any, Optional

from app.config import get_settings
from app.prompts.templates import build_mcq_prompt, build_opening_question_prompt

# Rotating pool when MOCK_LLM=true (no llama.cpp binary)
MOCK_OPENING = [
    "Tell me about your most relevant experience for {job}.",
    "What attracted you to apply for this {job} role?",
    "Walk me through your background in two minutes.",
]

MOCK_FOLLOWUPS = [
    "What was your specific contribution on that project?",
    "Which technologies did you use, and why did you choose them?",
    "How did you handle conflicting priorities or tight deadlines?",
    "What metrics or outcomes proved that work was successful?",
    "What would you do differently if you faced that situation again?",
    "How did you collaborate with teammates or stakeholders?",
    "Describe a technical decision you made and the trade-offs involved.",
    "What was the hardest bug or issue you solved in that context?",
]


def _run_llama(prompt: str, max_tokens: Optional[int] = None) -> str:
    settings = get_settings()
    if settings.mock_llm:
        return _mock_response(prompt)

    model_path = settings.llama_model
    if not __import__("os").path.isfile(model_path):
        return _mock_response(prompt)

    cmd = [
        settings.llama_bin,
        "-m", model_path,
        "-p", prompt,
        "-n", str(max_tokens or settings.llama_max_tokens),
        "--temp", "0.3",
        "-ngl", str(settings.llama_ngl),
        "-t", str(settings.llama_threads),
        "--no-display-prompt",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace"
        )
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return _mock_response(prompt, error=str(e))


def _pick_unique(candidates: list[str], asked: list[str]) -> str:
    asked_lower = {q.strip().lower() for q in asked}
    for q in candidates:
        if q.strip().lower() not in asked_lower:
            return q
    # All used — pick by turn index
    return candidates[len(asked) % len(candidates)]


def _mock_followup(job_title: str, asked: list[str]) -> str:
    templates = [t.format(job=job_title) if "{job}" in t else t for t in MOCK_FOLLOWUPS]
    return _pick_unique(templates, asked)


def _mock_response(prompt: str, error: str = "") -> str:
    if "JSON array" in prompt or "multiple choice" in prompt.lower():
        return json.dumps(_mock_mcq_questions(prompt))
    if "content_score" in prompt:
        return json.dumps({"content_score": 72, "rationale": "Mock: adequate coverage of key points."})
    if "Already asked" in prompt or "follow-up" in prompt.lower() or "follow up" in prompt.lower():
        asked = _extract_asked_from_prompt(prompt)
        job = "Software Engineer"
        m = re.search(r"interviewer for (?:the role: )?([^.\n]+)", prompt, re.I)
        if m:
            job = m.group(1).strip()
        return _mock_followup(job, asked)
    if "opening interview" in prompt.lower() or "opening question" in prompt.lower():
        asked = []
        job = "this role"
        m = re.search(r"role:\s*([^.]+)", prompt, re.I)
        if m:
            job = m.group(1).strip()
        return _pick_unique([t.format(job=job) for t in MOCK_OPENING], asked)
    return json.dumps({"text": "mock", "error": error})


def _extract_asked_from_prompt(prompt: str) -> list[str]:
    asked = []
    for m in re.finditer(r"Q:\s*([^A]+?)(?:\s+A:|$)", prompt):
        q = m.group(1).strip()
        if q and len(q) > 10:
            asked.append(q)
    return asked


def _mock_mcq_questions(prompt: str) -> list[dict]:
    job = "Software Engineer"
    m = re.search(r"job:\s*([^.]+)", prompt, re.I)
    if m:
        job = m.group(1).strip()
    questions = []
    for i in range(1, 21):
        questions.append({
            "id": i,
            "question_text": f"[{job}] Sample question {i}: Which approach best applies?",
            "options": {
                "A": f"Option A for Q{i}",
                "B": f"Option B for Q{i}",
                "C": f"Option C for Q{i}",
                "D": f"Option D for Q{i}",
            },
            "correct_option": "B" if i % 4 != 0 else "A",
            "difficulty": ["easy", "medium", "hard"][i % 3],
            "rationale": f"Option B is correct for question {i} in mock data.",
        })
    return questions


def extract_json_array(text: str) -> list[Any]:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def extract_json_object(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def generate_mcq(job_title: str) -> list[dict]:
    prompt = build_mcq_prompt(job_title)
    raw = _run_llama(prompt, max_tokens=4096)
    data = extract_json_array(raw)
    return _normalize_mcq(data)


def _normalize_mcq(items: list) -> list[dict]:
    out = []
    for i, q in enumerate(items[:20]):
        opts = q.get("options") or {}
        if isinstance(opts, list) and len(opts) >= 4:
            opts = {"A": opts[0], "B": opts[1], "C": opts[2], "D": opts[3]}
        out.append({
            "id": q.get("id", i + 1),
            "question_text": q.get("question_text", ""),
            "options": opts,
            "correct_option": str(q.get("correct_option", "A")).upper()[:1],
            "difficulty": q.get("difficulty", "medium"),
            "rationale": q.get("rationale", ""),
        })
    return out


def generate_opening_question(job_title: str, asked: Optional[list[str]] = None) -> str:
    asked = asked or []
    if get_settings().mock_llm:
        q = _pick_unique([t.format(job=job_title) for t in MOCK_OPENING], asked)
        return q
    prompt = build_opening_question_prompt(job_title)
    raw = _run_llama(prompt, max_tokens=80)
    text = raw.split("\n")[0].strip()[:250]
    if text.lower() in {a.lower() for a in asked}:
        return _mock_followup(job_title, asked)
    return text


def generate_followup(
    job_title: str,
    answer: str,
    context: str,
    asked_questions: Optional[list[str]] = None,
) -> str:
    from app.prompts.templates import build_followup_prompt
    asked = asked_questions or []
    prompt = build_followup_prompt(job_title, answer, context, asked)
    raw = _run_llama(prompt, max_tokens=80)
    text = raw.split("\n")[0].strip()[:250]
    # Reject duplicate or near-duplicate
    if any(text.lower() == q.lower() for q in asked):
        return _mock_followup(job_title, asked)
    return text


def score_content(answer: str, expected_points: str) -> dict:
    from app.prompts.templates import build_content_scoring_prompt
    prompt = build_content_scoring_prompt(answer, expected_points)
    raw = _run_llama(prompt, max_tokens=128)
    try:
        return extract_json_object(raw)
    except json.JSONDecodeError:
        return {"content_score": 50, "rationale": "Could not parse LLM score."}
