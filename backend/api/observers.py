"""
Observer API — public read-only endpoints, exports, news feed.
"""
import json
import csv
import io
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session

from backend.database import (
    Agent, DebateSession, DebateMessage, KnowledgeFact,
    Theory, NewsEvent, ApexPrediction, get_db
)
from backend.core.news_feed import get_recent_events

router = APIRouter(prefix="/api", tags=["observers"])


@router.get("/news")
def get_news(domain: str = "f1", limit: int = 20, db: Session = Depends(get_db)):
    events = get_recent_events(db, domain, limit)
    return [
        {
            "id": e.id,
            "headline": e.headline,
            "content": e.content,
            "event_type": e.event_type,
            "published_at": e.published_at.isoformat(),
            "processed": e.processed,
        }
        for e in events
    ]


@router.get("/stats")
def platform_stats(db: Session = Depends(get_db)):
    return {
        "agents": {
            "total": db.query(Agent).filter(Agent.status == "active").count(),
            "tier1": db.query(Agent).filter(Agent.tier == 1, Agent.status == "active").count(),
            "tier2": db.query(Agent).filter(Agent.tier == 2, Agent.status == "active").count(),
            "tier3": db.query(Agent).filter(Agent.tier == 3, Agent.status == "active").count(),
        },
        "debates": {
            "total": db.query(DebateSession).count(),
            "completed": db.query(DebateSession).filter(DebateSession.status == "completed").count(),
            "active": db.query(DebateSession).filter(DebateSession.status == "active").count(),
        },
        "knowledge": {
            "total_facts": db.query(KnowledgeFact).count(),
            "seed_facts": db.query(KnowledgeFact).filter(KnowledgeFact.is_seed == True).count(),
            "validated_theories": db.query(Theory).filter(Theory.status == "validated").count(),
            "pending_theories": db.query(Theory).filter(Theory.status == "pending").count(),
        },
        "predictions": {
            "total": db.query(ApexPrediction).count(),
            "validated_true": db.query(ApexPrediction).filter(ApexPrediction.status == "true").count(),
        },
        "news_events": {
            "total": db.query(NewsEvent).count(),
            "unprocessed": db.query(NewsEvent).filter(NewsEvent.processed == False).count(),
        },
    }


@router.get("/export/debates/{debate_id}")
def export_debate(debate_id: int, db: Session = Depends(get_db)):
    d = db.query(DebateSession).filter(DebateSession.id == debate_id).first()
    if not d:
        return JSONResponse(status_code=404, content={"detail": "Debate not found"})

    messages = (
        db.query(DebateMessage)
        .filter(DebateMessage.debate_id == debate_id)
        .order_by(DebateMessage.timestamp)
        .all()
    )
    agents_map = {
        a.id: a.name
        for a in db.query(Agent).filter(Agent.id.in_(d.get_participant_ids())).all()
    }

    data = {
        "debate_id": d.id,
        "topic": d.topic,
        "domain": d.domain,
        "started_at": d.started_at.isoformat(),
        "ended_at": d.ended_at.isoformat() if d.ended_at else None,
        "summary": d.summary,
        "participants": list(agents_map.values()),
        "messages": [
            {
                "agent": agents_map.get(m.agent_id, "Unknown"),
                "round": m.round_number,
                "type": m.msg_type,
                "content": m.content,
                "timestamp": m.timestamp.isoformat(),
            }
            for m in messages
        ],
    }

    return StreamingResponse(
        io.BytesIO(json.dumps(data, indent=2).encode()),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=debate_{debate_id}.json"},
    )


@router.get("/export/knowledge")
def export_knowledge(domain: str = "f1", db: Session = Depends(get_db)):
    facts = (
        db.query(KnowledgeFact)
        .filter(KnowledgeFact.domain == domain)
        .order_by(KnowledgeFact.confidence.desc())
        .all()
    )

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["id", "title", "content", "confidence", "is_seed", "created_at"])
    writer.writeheader()
    for f in facts:
        writer.writerow({
            "id": f.id,
            "title": f.title,
            "content": f.content[:500],
            "confidence": f.confidence,
            "is_seed": f.is_seed,
            "created_at": f.created_at.isoformat(),
        })

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=apex_knowledge_{domain}.csv"},
    )


@router.get("/export/theories")
def export_theories(domain: str = "f1", db: Session = Depends(get_db)):
    theories = (
        db.query(Theory)
        .filter(Theory.domain == domain)
        .order_by(Theory.created_at.desc())
        .all()
    )
    agents_map = {a.id: a.name for a in db.query(Agent).all()}
    data = [
        {
            "id": t.id,
            "agent": agents_map.get(t.agent_id, "Unknown"),
            "title": t.title,
            "content": t.content,
            "evidence": t.evidence,
            "confidence": t.confidence,
            "status": t.status,
            "created_at": t.created_at.isoformat(),
        }
        for t in theories
    ]
    return StreamingResponse(
        io.BytesIO(json.dumps(data, indent=2).encode()),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=apex_theories.json"},
    )
