from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import KnowledgeFact, Theory, Agent, get_db
from backend.core.cascade import validate_theory as run_validate

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("")
def list_facts(
    domain: str = "f1",
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    is_seed: Optional[bool] = None,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(KnowledgeFact).filter(
        KnowledgeFact.domain == domain,
        KnowledgeFact.confidence >= min_confidence,
    )
    if is_seed is not None:
        q = q.filter(KnowledgeFact.is_seed == is_seed)
    facts = q.order_by(KnowledgeFact.confidence.desc()).limit(limit).all()
    return [
        {
            "id": f.id,
            "title": f.title,
            "content": f.content,
            "confidence": f.confidence,
            "is_seed": f.is_seed,
            "source_theory_id": f.source_theory_id,
            "created_at": f.created_at.isoformat(),
        }
        for f in facts
    ]


@router.get("/theories")
def list_theories(
    domain: str = "f1",
    status: Optional[str] = None,
    limit: int = Query(30, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(Theory).filter(Theory.domain == domain)
    if status:
        q = q.filter(Theory.status == status)
    theories = q.order_by(Theory.created_at.desc()).limit(limit).all()
    agents = {a.id: a.name for a in db.query(Agent).all()}
    return [
        {
            "id": t.id,
            "title": t.title,
            "content": t.content,
            "evidence": t.evidence,
            "confidence": t.confidence,
            "status": t.status,
            "agent": agents.get(t.agent_id, "Unknown"),
            "debate_id": t.debate_id,
            "created_at": t.created_at.isoformat(),
        }
        for t in theories
    ]


@router.post("/theories/{theory_id}/validate")
async def validate_theory_endpoint(theory_id: int, db: Session = Depends(get_db)):
    """Manually trigger T2 validation of a pending theory."""
    result = await run_validate(theory_id, db)
    return result


@router.get("/search")
def search_knowledge(
    q: str,
    domain: str = "f1",
    db: Session = Depends(get_db),
):
    q_lower = q.lower()
    facts = (
        db.query(KnowledgeFact)
        .filter(KnowledgeFact.domain == domain)
        .all()
    )
    matched = [
        f for f in facts
        if any(word in (f.title + " " + f.content).lower() for word in q_lower.split())
    ]
    return [
        {
            "id": f.id,
            "title": f.title,
            "content": f.content[:400],
            "confidence": f.confidence,
        }
        for f in matched[:10]
    ]
