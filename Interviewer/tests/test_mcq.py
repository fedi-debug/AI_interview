"""MCQ endpoint and grading tests."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.environ["MOCK_LLM"] = "true"

from app.services.mcq_service import grade_submission, map_skills_to_profile
from app.services.llama_client import generate_mcq, extract_json_array


def test_mock_mcq_generation():
    qs = generate_mcq("Software Engineer")
    assert len(qs) == 20
    assert qs[0]["correct_option"] in "ABCD"
    assert "options" in qs[0]


def test_grade_submission_logic():
    questions = [
        {"id": 1, "correct_option": "A", "difficulty": "easy"},
        {"id": 2, "correct_option": "B", "difficulty": "hard"},
    ]
    answers = [{"question_id": 1, "selected": "A"}, {"question_id": 2, "selected": "C"}]
    skill = map_skills_to_profile(questions, answers, "software engineer")
    assert "_overall_fit" in skill


def test_extract_json_array():
    raw = '```json\n[{"id":1}]\n```'
    assert extract_json_array(raw)[0]["id"] == 1


@pytest.mark.asyncio
async def test_mcq_api(client):
    r = await client.post("/mcq/generate", json={"job_title": "Data Scientist"})
    assert r.status_code == 200
    data = r.json()
    assert "session_id" in data
    assert len(data["questions"]) == 20
    sid = data["session_id"]
    answers = [
        {"question_id": q["id"], "selected": q["correct_option"]}
        for q in data["questions"]
    ]
    r2 = await client.post(f"/mcq/{sid}/submit", json={"answers": answers})
    assert r2.status_code == 200
    assert r2.json()["score_percent"] == 100.0
