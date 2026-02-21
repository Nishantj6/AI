from typing import Optional, List
import asyncio
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import DebateSession, DebateMessage, Agent, get_db
from backend.core.debate_engine import run_debate, trigger_debate_from_news
from backend.core import broadcaster

router = APIRouter(prefix="/api/debates", tags=["debates"])


class TriggerRequest(BaseModel):
    topic: Optional[str] = None
    participants: Optional[List[str]] = None


@router.get("")
def list_debates(limit: int = 20, db: Session = Depends(get_db)):
    debates = (
        db.query(DebateSession)
        .order_by(DebateSession.started_at.desc())
        .limit(limit)
        .all()
    )
    result = []
    for d in debates:
        participant_ids = d.get_participant_ids()
        agents = db.query(Agent).filter(Agent.id.in_(participant_ids)).all()
        result.append({
            "id": d.id,
            "topic": d.topic,
            "domain": d.domain,
            "status": d.status,
            "participants": [a.name for a in agents],
            "summary": d.summary,
            "verdict": d.verdict,
            "verdict_confidence": d.verdict_confidence,
            "verdict_scores": json.loads(d.verdict_scores) if d.verdict_scores else {},
            "started_at": d.started_at.isoformat(),
            "ended_at": d.ended_at.isoformat() if d.ended_at else None,
        })
    return result


@router.get("/{debate_id}")
def get_debate(debate_id: int, db: Session = Depends(get_db)):
    d = db.query(DebateSession).filter(DebateSession.id == debate_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Debate not found")

    messages = (
        db.query(DebateMessage)
        .filter(DebateMessage.debate_id == debate_id)
        .order_by(DebateMessage.timestamp)
        .all()
    )

    participant_ids = d.get_participant_ids()
    agents_map = {a.id: a.name for a in db.query(Agent).filter(Agent.id.in_(participant_ids)).all()}

    return {
        "id": d.id,
        "topic": d.topic,
        "domain": d.domain,
        "status": d.status,
        "summary": d.summary,
        "started_at": d.started_at.isoformat(),
        "ended_at": d.ended_at.isoformat() if d.ended_at else None,
        "participants": list(agents_map.values()),
        "messages": [
            {
                "id": m.id,
                "agent": agents_map.get(m.agent_id, "Unknown"),
                "content": m.content,
                "msg_type": m.msg_type,
                "round": m.round_number,
                "timestamp": m.timestamp.isoformat(),
            }
            for m in messages
        ],
    }


@router.post("/trigger")
async def trigger_debate(req: TriggerRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Start a new debate. Uses latest news event if no topic provided."""
    if req.topic:
        topic = req.topic
        participants = req.participants

        async def run():
            from backend.database import SessionLocal
            _db = SessionLocal()
            try:
                async def broadcast(e):
                    await broadcaster.broadcast_to_debate(e["debate_id"], e)
                await run_debate(topic=topic, db=_db, participant_names=participants, broadcast=broadcast)
            finally:
                _db.close()

        background_tasks.add_task(run)
        return {"message": "Debate triggered", "topic": topic}
    else:
        async def run_from_news():
            from backend.database import SessionLocal
            _db = SessionLocal()
            try:
                async def broadcast(e):
                    await broadcaster.broadcast_to_debate(e["debate_id"], e)
                session = await trigger_debate_from_news(_db, broadcast=broadcast)
                if session:
                    await broadcaster.broadcast_to_debate(session.id, {
                        "type": "debate_end",
                        "debate_id": session.id,
                        "summary": session.summary,
                    })
            finally:
                _db.close()

        background_tasks.add_task(run_from_news)
        return {"message": "Debate triggered from latest news event"}


@router.websocket("/{debate_id}/stream")
async def debate_stream(websocket: WebSocket, debate_id: int):
    """WebSocket stream for a specific live debate."""
    await websocket.accept()
    broadcaster.add_debate_connection(debate_id, websocket)

    try:
        from backend.database import SessionLocal
        db = SessionLocal()
        try:
            d = db.query(DebateSession).filter(DebateSession.id == debate_id).first()
            if d:
                messages = db.query(DebateMessage).filter(
                    DebateMessage.debate_id == debate_id
                ).order_by(DebateMessage.timestamp).all()
                agents_map = {
                    a.id: a.name
                    for a in db.query(Agent).filter(
                        Agent.id.in_(d.get_participant_ids())
                    ).all()
                }
                for m in messages:
                    await websocket.send_json({
                        "type": "historical",
                        "agent": agents_map.get(m.agent_id, "Unknown"),
                        "content": m.content,
                        "round": m.round_number,
                        "msg_type": m.msg_type,
                        "timestamp": m.timestamp.isoformat(),
                    })
        finally:
            db.close()

        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})

    except WebSocketDisconnect:
        pass
    finally:
        broadcaster.remove_debate_connection(debate_id, websocket)
