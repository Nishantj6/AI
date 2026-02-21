"""
Debate Engine — orchestrates multi-round T1 agent debates.
Streams messages to WebSocket connections in real-time.
"""
import asyncio
import json
from datetime import datetime
from typing import Callable, Awaitable
from sqlalchemy.orm import Session

from backend.database import (
    DebateSession, DebateMessage, Agent, Theory, NewsEvent
)
from backend.agents.base_agent import BaseAgent
from backend.agents.tier1.oracle import oracle
from backend.agents.tier1.vector import vector
from backend.agents.tier1.podium import podium
from backend.core.cascade import knowledge_lookup, validate_theory
from backend.core.news_feed import build_news_context, mark_processed


TIER1_AGENTS: dict[str, BaseAgent] = {
    "Oracle": oracle,
    "Vector": vector,
    "Podium": podium,
}

DEBATE_ROUNDS = [
    ("opening", "Round 1 — Opening Statement", 1),
    ("evidence", "Round 2 — Evidence & Rebuttal", 2),
    ("conclusion", "Round 3 — Conclusions & Theory Submission", 3),
]


async def run_debate(
    topic: str,
    db: Session,
    news_event: NewsEvent | None = None,
    participant_names: list[str] | None = None,
    broadcast: Callable[[dict], Awaitable[None]] | None = None,
) -> DebateSession:
    """
    Run a full 3-round debate between T1 agents.
    Optionally streams events to `broadcast(event_dict)`.
    """
    if participant_names is None:
        participant_names = list(TIER1_AGENTS.keys())

    # Get or create agent DB rows
    agents_db: dict[str, Agent] = {}
    for name in participant_names:
        row = db.query(Agent).filter(Agent.name == name).first()
        if row:
            agents_db[name] = row

    participant_ids = [agents_db[n].id for n in participant_names if n in agents_db]

    # Create debate session
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

    async def emit(event_type: str, agent_name: str, content: str, round_num: int = 0):
        if broadcast:
            await broadcast({
                "type": event_type,
                "agent": agent_name,
                "content": content,
                "round": round_num,
                "debate_id": session.id,
                "timestamp": datetime.utcnow().isoformat(),
            })

    # Broadcast start
    await emit("debate_start", "system", f"Debate started: {topic}", 0)

    # Build conversation history per agent across rounds
    conversation_histories: dict[str, list[dict]] = {n: [] for n in participant_names}
    all_messages_so_far: list[str] = []

    submitted_theories: list[dict] = []

    for round_key, round_label, round_num in DEBATE_ROUNDS:
        await emit("round_start", "system", round_label, round_num)

        for agent_name in participant_names:
            agent = TIER1_AGENTS.get(agent_name)
            if not agent:
                continue

            # Build user message for this round
            prior_discussion = (
                "\n\n".join(all_messages_so_far[-6:])
                if all_messages_so_far
                else "This is the opening round."
            )

            round_instructions = {
                "opening": (
                    f"Topic: '{topic}'\n\n"
                    f"{news_context}\n\n"
                    "Give your opening statement. State your core thesis on this topic "
                    "clearly and concisely. Use search_knowledge_base() if helpful."
                ),
                "evidence": (
                    f"Topic: '{topic}'\n\nPrior discussion:\n{prior_discussion}\n\n"
                    "Present evidence supporting your thesis and respond to what the "
                    "other agents have said. Challenge weak claims. Be specific."
                ),
                "conclusion": (
                    f"Topic: '{topic}'\n\nFull discussion so far:\n{prior_discussion}\n\n"
                    "Give your final conclusion. If you have a well-reasoned, evidence-backed "
                    "theory (confidence ≥ 0.65), use submit_theory() to submit it formally."
                ),
            }

            user_msg = round_instructions[round_key]
            conversation_histories[agent_name].append({"role": "user", "content": user_msg})

            # Stream the agent's response
            full_response = []

            async def lookup(q: str, mc: float = 0.5, _db=db):
                return await knowledge_lookup(q, mc, _db)

            # Track submitted theories from tool calls
            theory_buffer = {}

            async def streaming_broadcast(chunk: str):
                full_response.append(chunk)
                if broadcast:
                    await broadcast({
                        "type": "agent_chunk",
                        "agent": agent_name,
                        "content": chunk,
                        "round": round_num,
                        "debate_id": session.id,
                        "timestamp": datetime.utcnow().isoformat(),
                    })

            # Run agent response with streaming
            response_text = []
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

            # Store message in DB
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

            # Add to conversation history and running summary
            conversation_histories[agent_name].append(
                {"role": "assistant", "content": full_text}
            )
            all_messages_so_far.append(f"{agent_name}: {full_text}")

            await emit("agent_done", agent_name, full_text, round_num)

            # Small delay between agents for readability
            await asyncio.sleep(0.5)

    # Close debate
    session.status = "completed"
    session.ended_at = datetime.utcnow()

    # Generate summary
    summary_msgs = [
        {
            "role": "user",
            "content": (
                f"Summarise this F1 debate on '{topic}' in 3–4 bullet points. "
                f"Identify points of agreement, disagreement, and the strongest theory proposed.\n\n"
                + "\n\n".join(all_messages_so_far)
            ),
        }
    ]
    summary = await oracle.respond_full(summary_msgs)
    session.summary = summary
    db.commit()

    await emit("debate_end", "system", summary, 0)

    return session


async def trigger_debate_from_news(db: Session, broadcast=None) -> DebateSession | None:
    """Find the most recent unprocessed news event and trigger a debate."""
    from backend.core.news_feed import get_latest_unprocessed

    events = get_latest_unprocessed(db, "f1", limit=1)
    if not events:
        return None

    event = events[0]
    topic = (
        f"Analysis: {event.headline}\n\n"
        f"Context: {event.content[:300]}"
    )
    return await run_debate(topic, db, news_event=event, broadcast=broadcast)
