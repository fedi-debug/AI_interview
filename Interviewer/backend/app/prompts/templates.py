"""LLM prompt templates for llama.cpp."""

MCQ_GENERATION_PROMPT = (
    "Generate 20 multiple choice questions for the job: {job_title}. "
    "For each question provide: id, question_text, options A–D, correct_option, "
    "difficulty (easy/medium/hard), and a one-line rationale for the correct answer. "
    "Output must be a JSON array."
)

OPENING_QUESTION_PROMPT = (
    "You are a professional interviewer for the role: {job_title}. "
    "Ask one clear opening interview question (technical or behavioral). "
    "Output only the question sentence, under 30 words, no preamble."
)

FOLLOWUP_PROMPT = (
    "You are an interviewer for {job_title}. Given the candidate's last answer: "
    "'{answer}' and the transcript context: '{context}'. "
    "Already asked (do NOT repeat or rephrase these): {asked}. "
    "Generate one NEW concise follow-up question that probes a different angle. "
    "Under 25 words. Output only the question sentence."
)

CONTENT_SCORING_PROMPT = (
    "Evaluate the candidate's answer: '{answer}' against the expected key points: "
    "'{expected_points}'. Return a JSON object with fields: content_score (0–100), "
    "rationale (one sentence)."
)


def build_mcq_prompt(job_title: str) -> str:
    return MCQ_GENERATION_PROMPT.format(job_title=job_title)


def build_opening_question_prompt(job_title: str) -> str:
    return OPENING_QUESTION_PROMPT.format(job_title=job_title)


def build_followup_prompt(
    job_title: str, answer: str, context: str, asked: list[str] | None = None
) -> str:
    asked_txt = " | ".join((asked or [])[-8:]) or "(none)"
    return FOLLOWUP_PROMPT.format(
        job_title=job_title,
        answer=answer[:500],
        context=context[:1500],
        asked=asked_txt[:1200],
    )


def build_content_scoring_prompt(answer: str, expected_points: str) -> str:
    return CONTENT_SCORING_PROMPT.format(
        answer=answer[:500], expected_points=expected_points[:800]
    )
