from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import Agent, EvaluationResult, get_db
from backend.core.evaluation import run_evaluation

router = APIRouter(prefix="/api/agents", tags=["agents"])


class ApplyRequest(BaseModel):
    applicant_name: str
    domain: str = "f1"
    requested_tier: int
    model_id: str
    bio: str = ""
    specialty: str = ""
    answers: dict[str, str]  # {question_id: answer}


@router.get("")
def list_agents(
    tier: Optional[int] = None,
    domain: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Agent).filter(Agent.status == "active")
    if tier is not None:
        q = q.filter(Agent.tier == tier)
    if domain:
        q = q.filter(Agent.domain == domain)
    agents = q.order_by(Agent.tier, Agent.name).all()
    return [
        {
            "id": a.id,
            "name": a.name,
            "tier": a.tier,
            "domain": a.domain,
            "specialty": a.specialty,
            "model_id": a.model_id,
            "bio": a.bio,
            "wins": a.wins,
            "created_at": a.created_at.isoformat(),
        }
        for a in agents
    ]


@router.get("/{agent_id}")
def get_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    from backend.database import DebateMessage, Theory
    debates = (
        db.query(DebateMessage)
        .filter(DebateMessage.agent_id == agent_id)
        .count()
    )
    theories = (
        db.query(Theory)
        .filter(Theory.agent_id == agent_id)
        .all()
    )

    return {
        "id": agent.id,
        "name": agent.name,
        "tier": agent.tier,
        "domain": agent.domain,
        "specialty": agent.specialty,
        "model_id": agent.model_id,
        "bio": agent.bio,
        "wins": agent.wins,
        "status": agent.status,
        "created_at": agent.created_at.isoformat(),
        "debate_messages_count": debates,
        "theories": [
            {
                "id": t.id,
                "title": t.title,
                "status": t.status,
                "confidence": t.confidence,
                "created_at": t.created_at.isoformat(),
            }
            for t in theories[-5:]
        ],
    }


@router.post("/apply")
async def apply_for_tier(req: ApplyRequest, db: Session = Depends(get_db)):
    existing = db.query(Agent).filter(Agent.name == req.applicant_name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Agent '{req.applicant_name}' already exists")

    if req.requested_tier not in (1, 2, 3):
        raise HTTPException(status_code=400, detail="Tier must be 1, 2, or 3")

    result = await run_evaluation(
        applicant_name=req.applicant_name,
        domain=req.domain,
        requested_tier=req.requested_tier,
        model_id=req.model_id,
        answers=req.answers,
        bio=req.bio,
        specialty=req.specialty,
        db=db,
    )

    return {
        "evaluation_id": result.id,
        "applicant_name": result.applicant_name,
        "status": result.status,
        "total_score": round(result.total_score or 0, 2),
        "threshold": result.threshold,
        "reviewer_notes": result.reviewer_notes,
        "completed_at": result.completed_at.isoformat() if result.completed_at else None,
        "message": (
            f"Congratulations! {req.applicant_name} has been admitted to Tier {req.requested_tier}."
            if result.status == "passed"
            else f"Application failed. Score: {result.total_score:.1f}% (required: {result.threshold}%)"
        ),
    }


@router.get("/apply/tests/{domain}/{tier}")
def get_test_questions(domain: str, tier: int):
    """Return test questions for a given domain and tier (no answers)."""
    from backend.domains.f1.seed_data import TIER1_TESTS, TIER2_TESTS, TIER3_TESTS, TIER_THRESHOLDS
    tests_map = {1: TIER1_TESTS, 2: TIER2_TESTS, 3: TIER3_TESTS}
    tests = tests_map.get(tier, [])
    return {
        "domain": domain,
        "tier": tier,
        "threshold": TIER_THRESHOLDS.get(tier),
        "questions": [{"id": t["id"], "question": t["question"], "max_score": t["max_score"]} for t in tests],
    }
