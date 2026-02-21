from typing import Optional, List
import json
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import KnowledgeFact, Theory, Agent, DebateSession, get_db
from backend.core.cascade import validate_theory as run_validate

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


def _fact_dict(f: KnowledgeFact) -> dict:
    return {
        "id": f.id,
        "title": f.title,
        "content": f.content,
        "confidence": f.confidence,
        "is_seed": f.is_seed,
        "source_theory_id": f.source_theory_id,
        "t2_lookups": f.t2_lookups or 0,
        "t3_lookups": f.t3_lookups or 0,
        "created_at": f.created_at.isoformat(),
    }


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
    return [_fact_dict(f) for f in facts]


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
    facts = db.query(KnowledgeFact).filter(KnowledgeFact.domain == domain).all()
    matched = [
        f for f in facts
        if any(word in (f.title + " " + f.content).lower() for word in q_lower.split())
    ]
    return [_fact_dict(f) for f in matched[:10]]


@router.get("/graph")
def knowledge_graph(domain: str = "f1", db: Session = Depends(get_db)):
    """
    Returns nodes and edges for the knowledge graph.
    Nodes: T1 agents, facts/theories.
    Edges: agent→theory (submitted), fact→agent (validated_by), fact→t2/t3 (looked up).
    """
    agents = {a.id: a for a in db.query(Agent).filter(Agent.domain == domain).all()}
    theories = db.query(Theory).filter(Theory.domain == domain).all()
    facts = db.query(KnowledgeFact).filter(KnowledgeFact.domain == domain).all()
    debates = db.query(DebateSession).filter(DebateSession.domain == domain).all()

    nodes = []
    edges = []
    seen_nodes = set()

    def add_node(node_id: str, label: str, node_type: str, **props):
        if node_id not in seen_nodes:
            seen_nodes.add(node_id)
            nodes.append({"id": node_id, "label": label, "type": node_type, **props})

    # Agent nodes
    for a in agents.values():
        add_node(f"agent_{a.id}", a.name, f"tier{a.tier}", tier=a.tier, specialty=a.specialty)

    # Theory nodes + edges from submitting agent
    for t in theories:
        tid = f"theory_{t.id}"
        add_node(tid, t.title[:50], "theory", status=t.status, confidence=t.confidence)
        if t.agent_id in agents:
            edges.append({"source": f"agent_{t.agent_id}", "target": tid, "type": "submitted"})

    # Fact nodes + validation edges
    for f in facts:
        fid = f"fact_{f.id}"
        label = f.title[:50]
        add_node(fid, label, "fact",
                 confidence=f.confidence,
                 is_seed=f.is_seed,
                 t2_lookups=f.t2_lookups or 0,
                 t3_lookups=f.t3_lookups or 0)

        # Edge from source theory → fact
        if f.source_theory_id:
            edges.append({"source": f"theory_{f.source_theory_id}", "target": fid, "type": "promoted_to_fact"})

        # Edge: validated_by agent → fact
        if f.validated_by and f.validated_by in agents:
            edges.append({"source": f"agent_{f.validated_by}", "target": fid, "type": "validated"})

        # Virtual T2/T3 usage edges
        if (f.t2_lookups or 0) > 0:
            # Find T2 agents
            t2_agents = [a for a in agents.values() if a.tier == 2]
            for ta in t2_agents:
                edges.append({"source": fid, "target": f"agent_{ta.id}", "type": "used_by_t2",
                               "weight": f.t2_lookups})
        if (f.t3_lookups or 0) > 0:
            t3_agents = [a for a in agents.values() if a.tier == 3]
            for ta in t3_agents:
                edges.append({"source": fid, "target": f"agent_{ta.id}", "type": "used_by_t3",
                               "weight": f.t3_lookups})

    # Debate verdict nodes
    for d in debates:
        if d.status == "completed" and d.verdict:
            did = f"debate_{d.id}"
            add_node(did, d.topic[:40], "debate",
                     verdict=d.verdict,
                     verdict_confidence=d.verdict_confidence,
                     summary=d.summary or "")
            for pid in d.get_participant_ids():
                if pid in agents:
                    edges.append({"source": f"agent_{pid}", "target": did, "type": "participated"})

    return {"nodes": nodes, "edges": edges}
