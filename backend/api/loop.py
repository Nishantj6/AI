"""
Loop control API — start/stop/status for the autonomous agent loop,
plus the global WebSocket feed that streams all debate events.
"""
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.core import broadcaster

router = APIRouter(prefix="/api/loop", tags=["loop"])


@router.get("/status")
def loop_status():
    from backend.core.autonomous_loop import get_status
    return get_status()


@router.post("/start")
async def loop_start():
    from backend.core import autonomous_loop
    from backend.core.broadcaster import broadcast_to_debate

    async def broadcast_fn(event: dict):
        await broadcast_to_debate(event.get("debate_id", 0), event)

    await autonomous_loop.start(broadcast_fn)
    return {"message": "Loop started", **autonomous_loop.get_status()}


@router.post("/stop")
async def loop_stop():
    from backend.core import autonomous_loop
    await autonomous_loop.stop()
    return {"message": "Loop stopped", **autonomous_loop.get_status()}


@router.websocket("/feed")
async def feed_stream(websocket: WebSocket):
    """Global event feed — receives ALL debate and loop events in real-time."""
    await websocket.accept()
    broadcaster.add_global_connection(websocket)

    try:
        # Replay recent buffered events so new clients get context
        for event in broadcaster.get_recent_events(40):
            try:
                await websocket.send_json(event)
            except Exception:
                break

        # Keep alive
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        broadcaster.remove_global_connection(websocket)
