"""
Knowledge Cascade — T1 theories → T2 validation → Knowledge Base.
"""
import json
from datetime import datetime
from sqlalchemy.orm import Session
from backend.database import Theory, KnowledgeFact, Agent
from backend.agents.tier2.validator import apex_val
from backend.agents.tier2.anomaly import apex_anom


async def knowledge_lookup(query: str, min_confidence: float, db: Session) -> list[dict]:
    """Search validated knowledge facts — used by agents as a tool callback."""
    query_lower = query.lower()
    facts = (
        db.query(KnowledgeFact)
        .filter(
            KnowledgeFact.confidence >= min_confidence,
        )
        .order_by(KnowledgeFact.confidence.desc())
        .limit(8)
        .all()
    )
    # Simple keyword match
    matched = [
        f for f in facts
        if any(word in (f.title + f.content).lower() for word in query_lower.split())
    ]
    if not matched:
        matched = facts[:5]

    return [
        {
            "id": f.id,
            "title": f.title,
            "content": f.content[:400],
            "confidence": f.confidence,
            "domain": f.domain,
        }
        for f in matched[:5]
    ]


async def validate_theory(theory_id: int, db: Session) -> dict:
    """Run a T2 validation pass on a pending theory."""
    theory = db.query(Theory).filter(Theory.id == theory_id).first()
    if not theory:
        return {"status": "error", "message": "Theory not found"}

    agent_row = db.query(Agent).filter(Agent.id == theory.agent_id).first()
    agent_name = agent_row.name if agent_row else "Unknown"

    # Build validation context
    validation_prompt = f"""Please validate the following F1 theory submitted by {agent_name}:

THEORY ID: {theory.id}
TITLE: {theory.title}
CONTENT: {theory.content}
EVIDENCE: {theory.evidence or 'None provided'}
CONFIDENCE: {theory.confidence}

Use search_knowledge_base() to cross-check against validated facts, then use validate_theory()
with the theory_id={theory.id} to record your verdict."""

    messages = [{"role": "user", "content": validation_prompt}]

    async def lookup(q: str, mc: float = 0.5):
        return await knowledge_lookup(q, mc, db)

    response = await apex_val.respond_full(messages, knowledge_lookup=lookup)

    # Parse verdict from response text
    verdict = "pending"
    if "validated" in response.lower() and "anomaly" not in response.lower():
        verdict = "validated"
    elif "anomaly" in response.lower():
        verdict = "anomaly"
    elif "rejected" in response.lower():
        verdict = "rejected"

    # Update theory status
    theory.status = verdict
    db.commit()

    # If validated, create a KnowledgeFact
    if verdict == "validated":
        val_agent = db.query(Agent).filter(Agent.name == apex_val.name).first()
        fact = KnowledgeFact(
            domain=theory.domain,
            title=theory.title,
            content=theory.content,
            source_theory_id=theory.id,
            validated_by=val_agent.id if val_agent else None,
            confidence=min(theory.confidence * 0.95, 0.95),
            tier_visibility=3,
        )
        db.add(fact)
        db.commit()

    return {
        "theory_id": theory_id,
        "verdict": verdict,
        "validator_response": response[:500],
    }


async def run_anomaly_scan(db: Session) -> list[dict]:
    """Ask Apex-Anom to scan recent facts for anomalies."""
    recent_facts = (
        db.query(KnowledgeFact)
        .order_by(KnowledgeFact.created_at.desc())
        .limit(20)
        .all()
    )
    facts_text = "\n".join(
        f"[{f.id}] {f.title}: {f.content[:200]}" for f in recent_facts
    )

    scan_prompt = (
        f"Please scan these recent F1 knowledge facts for anomalies, "
        f"contradictions, or data gaps:\n\n{facts_text}\n\n"
        "For each anomaly found, produce a structured anomaly report."
    )

    async def lookup(q: str, mc: float = 0.5):
        return await knowledge_lookup(q, mc, db)

    response = await apex_anom.respond_full(
        [{"role": "user", "content": scan_prompt}],
        knowledge_lookup=lookup,
    )

    return [{"scan_result": response, "scanned_at": datetime.utcnow().isoformat()}]


def seed_knowledge_facts(db: Session):
    """Insert seed facts from F1 knowledge base."""
    from backend.domains.f1.seed_data import SEED_FACTS
    if db.query(KnowledgeFact).filter(KnowledgeFact.is_seed == True).count() > 0:
        return
    for item in SEED_FACTS:
        fact = KnowledgeFact(
            domain="f1",
            title=item["title"],
            content=item["content"],
            confidence=item["confidence"],
            tier_visibility=3,
            is_seed=True,
        )
        db.add(fact)
    db.commit()
