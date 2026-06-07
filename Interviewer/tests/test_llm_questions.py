import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.environ["MOCK_LLM"] = "true"

from app.services.llama_client import generate_followup, generate_opening_question


def test_followups_are_unique():
    job = "Software Engineer"
    asked = [generate_opening_question(job)]
    for i in range(4):
        ans = f"Answer number {i} about my project work."
        ctx = " ".join(f"Q: {q}" for q in asked)
        q = generate_followup(job, ans, ctx, asked_questions=asked)
        assert q not in asked, f"Duplicate question: {q}"
        asked.append(q)
    assert len(set(asked)) == len(asked)
