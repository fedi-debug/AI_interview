"""llama.cpp subprocess client with varied mock interview questions."""

import json
import random
import re
import subprocess
from typing import Any, Optional

from app.config import get_settings
from app.prompts.templates import build_mcq_prompt, build_opening_question_prompt

MOCK_OPENING = {
    "en": [
        "Tell me about your most relevant experience for {job}.",
        "What attracted you to apply for this {job} role?",
        "Walk me through your background in two minutes.",
        "Which achievement best shows you are ready for this {job} role?",
        "What problem in your recent work best represents your strengths?",
        "How would you summarize your fit for this position?",
    ],
    "fr": [
        "Presentez-moi votre experience la plus pertinente pour le poste de {job}.",
        "Qu'est-ce qui vous a motive a postuler pour ce poste de {job} ?",
        "Pouvez-vous resumer votre parcours professionnel en deux minutes ?",
        "Quelle realisation montre le mieux que vous etes pret pour ce poste de {job} ?",
        "Quel probleme recent illustre le mieux vos points forts ?",
        "Comment resumeriez-vous votre adequation avec ce poste ?",
    ],
}

MOCK_FOLLOWUPS = {
    "en": [
        "What was your specific contribution on that project?",
        "Which technologies did you use, and why did you choose them?",
        "How did you handle conflicting priorities or tight deadlines?",
        "What metrics or outcomes proved that work was successful?",
        "What would you do differently if you faced that situation again?",
        "How did you collaborate with teammates or stakeholders?",
        "Describe a technical decision you made and the trade-offs involved.",
        "What was the hardest bug or issue you solved in that context?",
        "How did you validate that your solution was reliable?",
        "Tell me about a time you received difficult feedback.",
        "How do you break down ambiguous requirements?",
        "What risks did you identify, and how did you reduce them?",
        "How did you communicate progress to non-technical stakeholders?",
        "What did you learn from that experience?",
        "How do you prioritize quality when delivery pressure is high?",
        "Describe a situation where you had to learn a tool quickly.",
        "How did you measure your own performance on that work?",
        "What trade-off would you defend most strongly from that project?",
    ],
    "fr": [
        "Quelle a ete votre contribution precise dans ce projet ?",
        "Quelles technologies avez-vous utilisees, et pourquoi les avoir choisies ?",
        "Comment avez-vous gere des priorites contradictoires ou des delais serres ?",
        "Quels resultats ont prouve que ce travail etait reussi ?",
        "Que feriez-vous differemment si vous reviviez cette situation ?",
        "Comment avez-vous collabore avec l'equipe ou les parties prenantes ?",
        "Decrivez une decision technique importante et ses compromis.",
        "Quel a ete le probleme le plus difficile a resoudre dans ce contexte ?",
        "Comment avez-vous verifie que votre solution etait fiable ?",
        "Parlez-moi d'un retour difficile que vous avez recu.",
        "Comment decoupez-vous des besoins ambigus ?",
        "Quels risques avez-vous identifies, et comment les avez-vous reduits ?",
        "Comment avez-vous communique l'avancement a des interlocuteurs non techniques ?",
        "Qu'avez-vous appris de cette experience ?",
        "Comment maintenez-vous la qualite sous pression ?",
        "Decrivez une situation ou vous avez du apprendre rapidement un outil.",
        "Comment avez-vous mesure votre propre performance sur ce travail ?",
        "Quel compromis defendriez-vous le plus dans ce projet ?",
    ],
}


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
        "--temp", "0.5",
        "-ngl", str(settings.llama_ngl),
        "-t", str(settings.llama_threads),
        "--no-display-prompt",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8",
            errors="replace",
        )
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return _mock_response(prompt, error=str(e))


def _pick_unique(candidates: list[str], asked: list[str]) -> str:
    asked_lower = {q.strip().lower() for q in asked}
    unused = [q for q in candidates if q.strip().lower() not in asked_lower]
    if unused:
        return random.choice(unused)
    return candidates[len(asked) % len(candidates)]


def _mock_followup(job_title: str, asked: list[str], language: str = "en") -> str:
    templates = [
        t.format(job=job_title) if "{job}" in t else t
        for t in MOCK_FOLLOWUPS.get(language, MOCK_FOLLOWUPS["en"])
    ]
    return _pick_unique(templates, asked)


def _detect_prompt_language(prompt: str) -> str:
    return "fr" if "Language: French" in prompt or "Use French" in prompt else "en"


def _mock_response(prompt: str, error: str = "") -> str:
    language = _detect_prompt_language(prompt)
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
        return _mock_followup(job, asked, language)
    if "opening interview" in prompt.lower() or "opening question" in prompt.lower():
        asked = []
        job = "this role"
        m = re.search(r"role:\s*([^.]+)", prompt, re.I)
        if m:
            job = m.group(1).strip()
        return _pick_unique(
            [t.format(job=job) for t in MOCK_OPENING.get(language, MOCK_OPENING["en"])],
            asked,
        )
    return json.dumps({"text": "mock", "error": error})


def _extract_asked_from_prompt(prompt: str) -> list[str]:
    asked = []
    section = re.search(r"Already asked.*?:\s*(.*?)(?:\.\s*Generate|$)", prompt, re.I | re.S)
    if section:
        for q in section.group(1).split("|"):
            q = q.strip()
            if q and q != "(none)":
                asked.append(q)
        return asked

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


def generate_opening_question(
    job_title: str,
    asked: Optional[list[str]] = None,
    language: str = "en",
) -> str:
    asked = asked or []
    if get_settings().mock_llm:
        return _pick_unique(
            [t.format(job=job_title) for t in MOCK_OPENING.get(language, MOCK_OPENING["en"])],
            asked,
        )
    prompt = build_opening_question_prompt(job_title, language)
    raw = _run_llama(prompt, max_tokens=80)
    text = raw.split("\n")[0].strip()[:250]
    if text.lower() in {a.lower() for a in asked}:
        return _mock_followup(job_title, asked, language)
    return text


def generate_followup(
    job_title: str,
    answer: str,
    context: str,
    asked_questions: Optional[list[str]] = None,
    language: str = "en",
) -> str:
    from app.prompts.templates import build_followup_prompt

    asked = asked_questions or []
    prompt = build_followup_prompt(job_title, answer, context, asked, language)
    raw = _run_llama(prompt, max_tokens=80)
    text = raw.split("\n")[0].strip()[:250]
    if any(text.lower() == q.lower() for q in asked):
        return _mock_followup(job_title, asked, language)
    return text


def score_content(answer: str, expected_points: str) -> dict:
    from app.prompts.templates import build_content_scoring_prompt

    prompt = build_content_scoring_prompt(answer, expected_points)
    raw = _run_llama(prompt, max_tokens=128)
    try:
        return extract_json_object(raw)
    except json.JSONDecodeError:
        return {"content_score": 50, "rationale": "Could not parse LLM score."}
