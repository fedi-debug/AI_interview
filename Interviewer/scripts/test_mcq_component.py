#!/usr/bin/env python
"""Step 3 component test: MCQ generation (mock LLM)."""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.environ["MOCK_LLM"] = "true"

from app.services.llama_client import generate_mcq
from app.services.mcq_service import generate_and_store, grade_submission

if __name__ == "__main__":
    print("Generating MCQs for 'Software Engineer'...")
    result = generate_and_store("Software Engineer")
    sid = result["session_id"]
    print(f"Session: {sid}, questions: {len(result['questions'])}")
    print("Sample Q1:", result["questions"][0]["question_text"][:80])
    answers = [
        {"question_id": q["id"], "selected": q["correct_option"]}
        for q in result["questions"]
    ]
    graded = grade_submission(sid, answers)
    print("Score:", graded["score_percent"], "%")
    print("Skill map keys:", list(graded["skill_map"].keys())[:5])
    print("OK")
