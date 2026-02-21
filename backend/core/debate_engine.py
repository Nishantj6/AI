"""
Debate Engine — orchestrates multi-round T1 agent debates.
Streams messages to WebSocket connections in real-time.
Produces a Pass/Draw/Fail verdict with per-agent resolution scores.
"""
import asyncio
import json
import random
import re
from datetime import datetime
from typing import Callable, Optional, List
from sqlalchemy.orm import Session

from backend.database import (
    DebateSession, DebateMessage, Agent, Theory, NewsEvent
)
from backend.agents.base_agent import BaseAgent
from backend.agents.tier1.oracle import oracle
from backend.agents.tier1.vector import vector
from backend.agents.tier1.podium import podium
from backend.agents.tier1.falcon import falcon
from backend.agents.tier1.sigma import sigma
from backend.agents.tier1.circuit import circuit
from backend.agents.tier1.regs import regs
from backend.agents.tier1.storm import storm
from backend.agents.tier1.ledger import ledger
from backend.agents.tier1.rival import rival
from backend.agents.tier1.pitwall import pitwall
from backend.agents.tier1.radar import radar
from backend.core.cascade import knowledge_lookup, validate_theory
from backend.core.news_feed import build_news_context, mark_processed


ALL_TIER1_AGENTS: dict[str, BaseAgent] = {
    "Oracle":  oracle,
    "Vector":  vector,
    "Podium":  podium,
    "Falcon":  falcon,
    "Sigma":   sigma,
    "Circuit": circuit,
    "Regs":    regs,
    "Storm":   storm,
    "Ledger":  ledger,
    "Rival":   rival,
    "Pitwall": pitwall,
    "Radar":   radar,
}

DEBATE_ROUNDS = [
    ("opening",    "Round 1 — Opening Statement", 1),
    ("evidence",   "Round 2 — Evidence & Rebuttal", 2),
    ("conclusion", "Round 3 — Conclusions & Theory Submission", 3),
]

AGENTS_PER_DEBATE = 10


def _select_participants(requested: Optional[List[str]]) -> List[str]:
    if requested:
        valid = [n for n in requested if n in ALL_TIER1_AGENTS]
        if valid:
            return valid
    return random.sample(list(ALL_TIER1_AGENTS.keys()), AGENTS_PER_DEBATE)


def _extract_resolution_score(text: str) -> int:
    """Parse RESOLUTION: <n>/100 from agent conclusion."""
    m = re.search(r"RESOLUTION[:\s]+(\d+)\s*/\s*100", text, re.IGNORECASE)
    if m:
        return min(100, max(0, int(m.group(1))))
    m2 = re.search(r"(\d{2,3})\s*%\s*confident", text, re.IGNORECASE)
    if m2:
        return min(100, max(0, int(m2.group(1))))
    return 50


def _compute_verdict(scores: dict[str, int]) -> tuple[str, float]:
    """
    PASS  = avg ≥ 70  → strong evidence-based consensus
    FAIL  = avg ≤ 35  → position thoroughly undermined
    DRAW  = everything else
    Returns (verdict, confidence_pct)
    """
    if not scores:
        return "draw", 50.0
    avg = sum(scores.values()) / len(scores)
    if avg >= 70:
        return "pass", float(avg)
    elif avg <= 35:
        return "fail", float(100 - avg)
    else:
        return "draw", float(abs(avg - 50) * 2)


async def run_debate(
    topic: str,
    db: Session,
    news_event: Optional[NewsEvent] = None,
    participant_names: Optional[List[str]] = None,
    broadcast: Optional[Callable] = None,
) -> DebateSession:
    """Run a full 3-round debate. Picks 3 random T1 agents unless names supplied."""
    participant_names = _select_participants(participant_names)

    agents_db: dict[str, Agent] = {}
    for name in participant_names:
        row = db.query(Agent).filter(Agent.name == name).first()
        if row:
            agents_db[name] = row

    participant_ids = [agents_db[n].id for n in participant_names if n in agents_db]

    session = DebateSession(
        topic=topic,
        domain="f1",
        participant_ids=json.dumps(participant_ids),
        status="active",
        news_event_id=news_event.id if news_event else None,
        started_at=datetime.utcnow(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    if news_event:
        mark_processed(db, news_event.id, session.id)

    news_context = build_news_context([news_event] if news_event else [])

    async def emit(event_type: str, agent_name: str, content: str, round_num: int = 0, **extra):
        if broadcast:
            payload = {
                "type": event_type,
                "agent": agent_name,
                "content": content,
                "round": round_num,
                "debate_id": session.id,
                "timestamp": datetime.utcnow().isoformat(),
            }
            payload.update(extra)
            await broadcast(payload)

    await emit("debate_start", "system", f"Debate started: {topic}", 0)

    conversation_histories: dict[str, List[dict]] = {n: [] for n in participant_names}
    all_messages_so_far: List[str] = []

    for round_key, round_label, round_num in DEBATE_ROUNDS:
        await emit("round_start", "system", round_label, round_num)

        for agent_name in participant_names:
            agent = ALL_TIER1_AGENTS.get(agent_name)
            if not agent:
                continue

            prior_discussion = (
                "\n\n".join(all_messages_so_far[-6:])
                if all_messages_so_far
                else "This is the opening round."
            )
            other_agents = [n for n in participant_names if n != agent_name]
            other_str = " and ".join(other_agents) or "other agents"

            round_instructions = {
                "opening": (
                    f"DEBATE TOPIC: '{topic}'\n\n"
                    f"{news_context}\n\n"
                    f"Debating against: {other_str}.\n\n"
                    "Give your opening statement with a definitive, falsifiable position. "
                    "Vagueness will lose points. Cite specific mechanisms, data points, and "
                    "use search_knowledge_base() to anchor in validated facts. "
                    "Make your thesis clear in the first sentence."
                ),
                "evidence": (
                    f"DEBATE TOPIC: '{topic}'\n\nPrior discussion:\n{prior_discussion}\n\n"
                    "You MUST: (1) present hard, specific evidence for your thesis. "
                    "(2) Directly rebut at least one claim from another agent — name them "
                    "and explain precisely why they are wrong or incomplete. "
                    "(3) If you agree with a point, concede it and redirect. "
                    "Weak or vague rebuttals lose points. Be rigorous."
                ),
                "conclusion": (
                    f"DEBATE TOPIC: '{topic}'\n\nFull discussion:\n{prior_discussion}\n\n"
                    "Give your final conclusion. You MUST include:\n"
                    "RESOLUTION: <score>/100  (your confidence that your position is correct, "
                    "based on the evidence presented in this debate)\n\n"
                    "Then summarise your strongest arguments and concede any points you lost. "
                    "If your confidence ≥ 65, use submit_theory() to formally submit your position."
                ),
            }

            conversation_histories[agent_name].append(
                {"role": "user", "content": round_instructions[round_key]}
            )

            async def lookup(q: str, mc: float = 0.5, _db=db):
                return await knowledge_lookup(q, mc, _db, tier=1)

            response_text: List[str] = []
            async for chunk in agent.respond(
                conversation_histories[agent_name],
                knowledge_lookup=lookup,
                extra_context=news_context,
            ):
                response_text.append(chunk)
                if broadcast:
                    await broadcast({
                        "type": "agent_chunk",
                        "agent": agent_name,
                        "content": chunk,
                        "round": round_num,
                        "debate_id": session.id,
                        "timestamp": datetime.utcnow().isoformat(),
                    })

            full_text = "".join(response_text)

            db_row = agents_db.get(agent_name)
            if db_row:
                msg = DebateMessage(
                    debate_id=session.id,
                    agent_id=db_row.id,
                    content=full_text,
                    msg_type=round_key,
                    round_number=round_num,
                )
                db.add(msg)
                db.commit()

            conversation_histories[agent_name].append(
                {"role": "assistant", "content": full_text}
            )
            all_messages_so_far.append(f"**{agent_name}** ({agent.specialty}):\n{full_text}")

            await emit("agent_done", agent_name, full_text, round_num)
            await asyncio.sleep(0.5)

    # ── Scoring ────────────────────────────────────────────────────
    agent_scores: dict[str, int] = {}
    for agent_name in participant_names:
        conclusion = next(
            (m["content"] for m in reversed(conversation_histories[agent_name])
             if m["role"] == "assistant"),
            ""
        )
        agent_scores[agent_name] = _extract_resolution_score(conclusion)

    verdict, verdict_confidence = _compute_verdict(agent_scores)

    # Use the highest-scoring participant to write the summary — they earned it
    top_agent_name = max(agent_scores, key=agent_scores.get) if agent_scores else participant_names[0]
    summariser = ALL_TIER1_AGENTS[top_agent_name]

    summary_msgs = [
        {
            "role": "user",
            "content": (
                f"You are {top_agent_name}. You are concluding this debate as the highest-scoring participant.\n\n"
                f"DEBATE TOPIC: '{topic}'\n"
                f"VERDICT: {verdict.upper()} — {verdict_confidence:.0f}% resolution confidence\n"
                f"AGENT SCORES: {', '.join(f'{a}: {s}/100' for a, s in agent_scores.items())}\n\n"
                "Write a rigorous 3–4 bullet-point summary of this debate from your perspective:\n"
                "• What was the core question?\n"
                "• What was the strongest argument made (by any agent)?\n"
                "• Where did agents agree and disagree?\n"
                "• What is the definitive answer or conclusion the evidence supports?\n\n"
                + "\n\n".join(all_messages_so_far)
            ),
        }
    ]
    summary = await summariser.respond_full(summary_msgs)

    session.status = "completed"
    session.ended_at = datetime.utcnow()
    session.summary = summary
    session.verdict = verdict
    session.verdict_scores = json.dumps(agent_scores)
    session.verdict_confidence = verdict_confidence
    db.commit()

    await emit(
        "debate_end", "system", summary, 0,
        verdict=verdict,
        verdict_confidence=round(verdict_confidence, 1),
        agent_scores=agent_scores,
    )

    return session


async def trigger_debate_from_news(db: Session, broadcast=None) -> Optional[DebateSession]:
    """Find the most recent unprocessed news event and trigger a debate."""
    from backend.core.news_feed import get_latest_unprocessed

    events = get_latest_unprocessed(db, "f1", limit=1)
    if not events:
        return None

    event = events[0]
    topic = f"Analysis: {event.headline}\n\nContext: {event.content[:300]}"
    return await run_debate(topic, db, news_event=event, broadcast=broadcast)
