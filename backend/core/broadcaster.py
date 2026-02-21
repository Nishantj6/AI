"""
Centralized WebSocket broadcast registry.
Decoupled from any router so autonomous_loop and debates can both use it
without creating circular imports.
"""
from typing import Any

# Per-debate connections: {debate_id: [WebSocket, ...]}
_per_debate: dict[int, list] = {}

# Global feed connections (receive ALL events)
_global: list = []

# Rolling event buffer for late-joining feed clients
_buffer: list = []
BUFFER_SIZE = 120


async def broadcast_to_debate(debate_id: int, event: dict):
    """Broadcast a debate event to per-debate AND global listeners."""
    _buffer.append(event)
    if len(_buffer) > BUFFER_SIZE:
        _buffer.pop(0)

    for sockets, is_debate in [(_per_debate.get(debate_id, []), True), (_global, False)]:
        dead = []
        for ws in list(sockets):
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if is_debate:
                _per_debate.get(debate_id, []).remove(ws)
            else:
                if ws in _global:
                    _global.remove(ws)


async def broadcast_global(event: dict):
    """Send a loop-level event (not debate-specific) to the global feed."""
    _buffer.append(event)
    if len(_buffer) > BUFFER_SIZE:
        _buffer.pop(0)
    dead = []
    for ws in list(_global):
        try:
            await ws.send_json(event)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in _global:
            _global.remove(ws)


def add_debate_connection(debate_id: int, ws):
    if debate_id not in _per_debate:
        _per_debate[debate_id] = []
    _per_debate[debate_id].append(ws)


def remove_debate_connection(debate_id: int, ws):
    sockets = _per_debate.get(debate_id, [])
    if ws in sockets:
        sockets.remove(ws)


def add_global_connection(ws):
    _global.append(ws)


def remove_global_connection(ws):
    if ws in _global:
        _global.remove(ws)


def get_recent_events(n: int = 60) -> list:
    return _buffer[-n:]
