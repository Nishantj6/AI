from typing import Optional, List
import asyncio
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import DebateSession, DebateMessage, Agent, get_db
from backend.core.debate_engine import run_debate, trigger_debate_from_news

router = APIRouter(prefix="/api/debates", tags=["debates"])

# Active WebSocket connections per debate {debate_id: [ws, ...]}
_connections: dict[int, list[WebSocket]] = {}


async def broadcast_to_debate(debate_id: int, event: dict):
    sockets = _connections.get(debate_id, [])
    dead = []
    for ws in sockets:
        try:
            await ws.send_json(event)
        except Exception:
            dead.append(ws)
    for ws in dead:
        sockets.remove(ws)


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
    # Create a placeholder session to get an ID before running
    if req.topic:
        async def run():
            session = await run_debate(
                topic=req.topic,
                db=db,
                participant_names=req.participants,
                broadcast=lambda e: broadcast_to_debate(session.id, e),
            )

        background_tasks.add_task(run)
        return {"message": "Debate triggered", "topic": req.topic}
    else:
        async def run_from_news():
            from backend.database import SessionLocal
            _db = SessionLocal()
            try:
                session = await trigger_debate_from_news(_db)
                if session:
                    await broadcast_to_debate(session.id, {
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
    """WebSocket stream for live debate events."""
    await websocket.accept()

    if debate_id not in _connections:
        _connections[debate_id] = []
    _connections[debate_id].append(websocket)

    try:
        # Send current messages if debate exists
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

        # Keep connection alive
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})

    except WebSocketDisconnect:
        pass
    finally:
        if debate_id in _connections and websocket in _connections[debate_id]:
            _connections[debate_id].remove(websocket)
