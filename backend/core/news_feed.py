"""
News Feed — Mock F1 news event scheduler.
Returns unprocessed events and marks them as processed.
"""
from datetime import datetime
from sqlalchemy.orm import Session
from backend.database import NewsEvent
from backend.domains.f1.seed_data import SEED_NEWS


def seed_news_events(db: Session):
    """Insert seed news events if not already present."""
    if db.query(NewsEvent).count() > 0:
        return
    for item in SEED_NEWS:
        event = NewsEvent(
            domain="f1",
            headline=item["headline"],
            content=item["content"],
            event_type=item["event_type"],
            published_at=item["published_at"],
            processed=False,
        )
        db.add(event)
    db.commit()


def get_latest_unprocessed(db: Session, domain: str = "f1", limit: int = 5) -> list[NewsEvent]:
    return (
        db.query(NewsEvent)
        .filter(NewsEvent.domain == domain, NewsEvent.processed == False)
        .order_by(NewsEvent.published_at.desc())
        .limit(limit)
        .all()
    )


def get_recent_events(db: Session, domain: str = "f1", limit: int = 20) -> list[NewsEvent]:
    return (
        db.query(NewsEvent)
        .filter(NewsEvent.domain == domain)
        .order_by(NewsEvent.published_at.desc())
        .limit(limit)
        .all()
    )


def mark_processed(db: Session, event_id: int, debate_id: int | None = None):
    event = db.query(NewsEvent).filter(NewsEvent.id == event_id).first()
    if event:
        event.processed = True
        if debate_id:
            event.triggered_debate_id = debate_id
        db.commit()


def build_news_context(events: list[NewsEvent]) -> str:
    if not events:
        return "No recent news events."
    lines = ["RECENT F1 NEWS:"]
    for ev in events:
        lines.append(f"[{ev.published_at.strftime('%d %b %Y')}] {ev.headline}")
        lines.append(f"  {ev.content[:300]}...")
    return "\n".join(lines)
