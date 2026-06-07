"""SQLite persistence for sessions, MCQ, transcripts, and features."""

import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


class SessionRow(Base):
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True)
    session_type = Column(String(32))  # mcq | interview
    job_title = Column(String(256))
    candidate_id = Column(String(64), nullable=True)
    consent_given = Column(Integer, default=0)
    human_review_required = Column(Integer, default=1)
    status = Column(String(32), default="created")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    metadata_json = Column(Text, default="{}")


class McqRow(Base):
    __tablename__ = "mcq_sets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), index=True)
    questions_json = Column(Text)
    answers_json = Column(Text, nullable=True)
    score = Column(Float, nullable=True)
    skill_map_json = Column(Text, nullable=True)


class TranscriptRow(Base):
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), index=True)
    segment_index = Column(Integer)
    text = Column(Text)
    start_ms = Column(Integer)
    end_ms = Column(Integer)
    confidence = Column(Float, nullable=True)


class FeatureRow(Base):
    __tablename__ = "features"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), index=True)
    timestamp_ms = Column(Integer)
    feature_type = Column(String(64))
    payload_json = Column(Text)


class ReportRow(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), unique=True, index=True)
    report_json = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def get_engine():
    from pathlib import Path as PathLib

    settings = get_settings()
    url = settings.database_url
    if url.startswith("sqlite:///"):
        path = url.replace("sqlite:///", "")
        PathLib(path).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, connect_args={"check_same_thread": False})


SessionLocal = sessionmaker(autocommit=False, autoflush=False)


def init_db():
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return engine


def get_db_session() -> Session:
    engine = init_db()
    return SessionLocal(bind=engine)


def save_session(
    session_id: str,
    session_type: str,
    job_title: str,
    *,
    candidate_id: Optional[str] = None,
    consent: bool = False,
    metadata: Optional[dict] = None,
) -> None:
    with get_db_session() as db:
        row = SessionRow(
            id=session_id,
            session_type=session_type,
            job_title=job_title,
            candidate_id=candidate_id,
            consent_given=1 if consent else 0,
            metadata_json=json.dumps(metadata or {}),
        )
        db.merge(row)
        db.commit()


def save_mcq(session_id: str, questions: list, answers: Optional[list] = None,
             score: Optional[float] = None, skill_map: Optional[dict] = None):
    with get_db_session() as db:
        existing = db.execute(
            select(McqRow).where(McqRow.session_id == session_id)
        ).scalar_one_or_none()
        if existing:
            existing.questions_json = json.dumps(questions)
            if answers is not None:
                existing.answers_json = json.dumps(answers)
            if score is not None:
                existing.score = score
            if skill_map is not None:
                existing.skill_map_json = json.dumps(skill_map)
        else:
            db.add(McqRow(
                session_id=session_id,
                questions_json=json.dumps(questions),
                answers_json=json.dumps(answers) if answers else None,
                score=score,
                skill_map_json=json.dumps(skill_map) if skill_map else None,
            ))
        db.commit()


def get_mcq(session_id: str) -> Optional[dict]:
    with get_db_session() as db:
        row = db.execute(
            select(McqRow).where(McqRow.session_id == session_id)
        ).scalar_one_or_none()
        if not row:
            return None
        return {
            "questions": json.loads(row.questions_json),
            "answers": json.loads(row.answers_json) if row.answers_json else None,
            "score": row.score,
            "skill_map": json.loads(row.skill_map_json) if row.skill_map_json else None,
        }


def append_transcript(session_id: str, segment_index: int, text: str,
                      start_ms: int, end_ms: int, confidence: float):
    with get_db_session() as db:
        db.add(TranscriptRow(
            session_id=session_id,
            segment_index=segment_index,
            text=text,
            start_ms=start_ms,
            end_ms=end_ms,
            confidence=confidence,
        ))
        db.commit()


def append_feature(session_id: str, timestamp_ms: int, feature_type: str, payload: dict):
    with get_db_session() as db:
        db.add(FeatureRow(
            session_id=session_id,
            timestamp_ms=timestamp_ms,
            feature_type=feature_type,
            payload_json=json.dumps(payload),
        ))
        db.commit()


def save_report(session_id: str, report: dict):
    with get_db_session() as db:
        existing = db.execute(
            select(ReportRow).where(ReportRow.session_id == session_id)
        ).scalar_one_or_none()
        if existing:
            existing.report_json = json.dumps(report)
        else:
            db.add(ReportRow(session_id=session_id, report_json=json.dumps(report)))
        db.commit()


def get_report(session_id: str) -> Optional[dict]:
    with get_db_session() as db:
        row = db.execute(
            select(ReportRow).where(ReportRow.session_id == session_id)
        ).scalar_one_or_none()
        return json.loads(row.report_json) if row else None
