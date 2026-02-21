import json
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Text,
    DateTime, Boolean, ForeignKey, event
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from backend.config import get_settings


settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)

# Enable WAL mode for better concurrent read performance
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    tier = Column(Integer, nullable=False)          # 1, 2, or 3
    domain = Column(String(50), nullable=False)     # e.g. "f1"
    specialty = Column(String(200), nullable=False)
    model_id = Column(String(100), nullable=False)
    system_prompt = Column(Text, nullable=False)
    bio = Column(Text, nullable=True)
    status = Column(String(20), default="active")   # active/pending/rejected
    wins = Column(Integer, default=0)               # Apex Award wins
    created_at = Column(DateTime, default=datetime.utcnow)


class Theory(Base):
    __tablename__ = "theories"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    domain = Column(String(50), nullable=False)
    title = Column(String(300), nullable=False)
    content = Column(Text, nullable=False)
    evidence = Column(Text, nullable=True)
    confidence = Column(Float, default=0.5)
    status = Column(String(30), default="pending")  # pending/validated/rejected/anomaly
    debate_id = Column(Integer, ForeignKey("debate_sessions.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class DebateSession(Base):
    __tablename__ = "debate_sessions"

    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String(500), nullable=False)
    domain = Column(String(50), nullable=False)
    participant_ids = Column(Text, nullable=False)  # JSON list of agent ids
    status = Column(String(20), default="active")   # active/completed/archived
    summary = Column(Text, nullable=True)
    news_event_id = Column(Integer, ForeignKey("news_events.id"), nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)

    def get_participant_ids(self) -> list[int]:
        return json.loads(self.participant_ids)


class DebateMessage(Base):
    __tablename__ = "debate_messages"

    id = Column(Integer, primary_key=True, index=True)
    debate_id = Column(Integer, ForeignKey("debate_sessions.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    content = Column(Text, nullable=False)
    msg_type = Column(String(30), default="statement")  # opening/evidence/rebuttal/conclusion/system
    round_number = Column(Integer, default=1)
    timestamp = Column(DateTime, default=datetime.utcnow)


class KnowledgeFact(Base):
    __tablename__ = "knowledge_facts"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String(50), nullable=False)
    title = Column(String(300), nullable=False)
    content = Column(Text, nullable=False)
    source_theory_id = Column(Integer, ForeignKey("theories.id"), nullable=True)
    validated_by = Column(Integer, ForeignKey("agents.id"), nullable=True)
    confidence = Column(Float, default=0.9)
    tier_visibility = Column(Integer, default=3)    # min tier that can see this
    is_seed = Column(Boolean, default=False)        # seeded base facts
    created_at = Column(DateTime, default=datetime.utcnow)


class ApexPrediction(Base):
    __tablename__ = "apex_predictions"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    claim = Column(Text, nullable=False)
    prediction_date = Column(DateTime, default=datetime.utcnow)
    domain = Column(String(50), nullable=False)
    season = Column(String(20), nullable=False)     # e.g. "2025"
    status = Column(String(20), default="pending")  # pending/true/false
    validation_date = Column(DateTime, nullable=True)
    validation_source = Column(String(500), nullable=True)
    accuracy_score = Column(Float, nullable=True)   # 0.0–1.0


class NewsEvent(Base):
    __tablename__ = "news_events"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String(50), nullable=False)
    headline = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    event_type = Column(String(50), nullable=False)  # race_result/regulation/technical/transfer
    published_at = Column(DateTime, nullable=False)
    processed = Column(Boolean, default=False)
    triggered_debate_id = Column(Integer, nullable=True)


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id = Column(Integer, primary_key=True, index=True)
    applicant_name = Column(String(100), nullable=False)
    domain = Column(String(50), nullable=False)
    requested_tier = Column(Integer, nullable=False)
    model_id = Column(String(100), nullable=False)
    bio = Column(Text, nullable=True)
    specialty = Column(String(200), nullable=True)
    scores = Column(Text, nullable=True)            # JSON {question_id: score}
    total_score = Column(Float, nullable=True)
    threshold = Column(Float, nullable=True)
    status = Column(String(20), default="pending")  # pending/passed/failed/reviewing
    reviewer_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
