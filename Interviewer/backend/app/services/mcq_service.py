"""MCQ generation, grading, and skill mapping."""

import uuid
from typing import Any

from app import db
from app.services.llama_client import generate_mcq

# Job profile skill weights (extend per role)
JOB_SKILL_PROFILES: dict[str, dict[str, float]] = {
    "software engineer": {
        "algorithms": 0.2,
        "system_design": 0.2,
        "coding": 0.25,
        "debugging": 0.15,
        "communication": 0.1,
        "tools": 0.1,
    },
    "data scientist": {
        "statistics": 0.25,
        "ml": 0.25,
        "python": 0.2,
        "sql": 0.15,
        "communication": 0.15,
    },
    "default": {
        "technical": 0.4,
        "problem_solving": 0.3,
        "communication": 0.2,
        "domain": 0.1,
    },
}

DIFFICULTY_WEIGHT = {"easy": 1.0, "medium": 1.5, "hard": 2.0}


def create_mcq_session(job_title: str, candidate_id: str | None = None) -> str:
    session_id = str(uuid.uuid4())
    db.save_session(session_id, "mcq", job_title, candidate_id=candidate_id)
    return session_id


def generate_and_store(job_title: str, session_id: str | None = None) -> dict[str, Any]:
    if not session_id:
        session_id = create_mcq_session(job_title)
    questions = generate_mcq(job_title)
    db.save_mcq(session_id, questions)
    db.save_session(session_id, "mcq", job_title, metadata={"question_count": len(questions)})
    return {"session_id": session_id, "questions": questions}


def grade_submission(session_id: str, answers: list[dict]) -> dict[str, Any]:
    """
    answers: [{"question_id": 1, "selected": "B"}, ...]
    """
    stored = db.get_mcq(session_id)
    if not stored:
        raise ValueError(f"MCQ session not found: {session_id}")
    questions = {q["id"]: q for q in stored["questions"]}
    correct = 0
    weighted = 0.0
    max_weight = 0.0
    per_question = []

    for ans in answers:
        qid = ans.get("question_id") or ans.get("id")
        selected = str(ans.get("selected", "")).upper()[:1]
        q = questions.get(qid)
        if not q:
            continue
        diff = q.get("difficulty", "medium")
        w = DIFFICULTY_WEIGHT.get(diff, 1.0)
        max_weight += w
        is_correct = selected == q["correct_option"]
        if is_correct:
            correct += 1
            weighted += w
        per_question.append({
            "question_id": qid,
            "selected": selected,
            "correct": is_correct,
            "difficulty": diff,
        })

    pct = (correct / len(questions) * 100) if questions else 0
    weighted_pct = (weighted / max_weight * 100) if max_weight else pct
    skill_map = map_skills_to_profile(
        stored["questions"], answers, job_title_from_session(session_id)
    )
    db.save_mcq(session_id, stored["questions"], answers, weighted_pct, skill_map)
    return {
        "session_id": session_id,
        "score_percent": round(weighted_pct, 2),
        "correct_count": correct,
        "total": len(questions),
        "per_question": per_question,
        "skill_map": skill_map,
    }


def job_title_from_session(session_id: str) -> str:
    with db.get_db_session() as sess:
        from app.db import SessionRow
        row = sess.get(SessionRow, session_id)
        return row.job_title if row else "default"


def map_skills_to_profile(
    questions: list[dict], answers: list[dict], job_title: str
) -> dict[str, float]:
    """Map MCQ performance to job skill weights."""
    key = job_title.lower().strip()
    profile = JOB_SKILL_PROFILES.get(key) or JOB_SKILL_PROFILES["default"]
    qmap = {q["id"]: q for q in questions}
    skill_scores: dict[str, list[float]] = {k: [] for k in profile}

    skills_list = list(profile.keys())
    for i, ans in enumerate(answers):
        qid = ans.get("question_id") or ans.get("id")
        q = qmap.get(qid)
        if not q:
            continue
        skill = skills_list[i % len(skills_list)]
        selected = str(ans.get("selected", "")).upper()[:1]
        skill_scores[skill].append(100.0 if selected == q["correct_option"] else 0.0)

    result = {}
    for skill, weight in profile.items():
        scores = skill_scores.get(skill, [])
        avg = sum(scores) / len(scores) if scores else 50.0
        result[skill] = round(avg * weight, 2)
    result["_profile"] = profile
    result["_overall_fit"] = round(sum(result[k] for k in profile), 2)
    return result
