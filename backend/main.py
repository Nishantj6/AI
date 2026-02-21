"""
Apex — Tiered AI Agent Knowledge Platform
FastAPI application entry point.
"""
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import get_settings
from backend.database import init_db, get_db, Agent, SessionLocal
from backend.api.agents import router as agents_router
from backend.api.debates import router as debates_router
from backend.api.knowledge import router as knowledge_router
from backend.api.award import router as award_router
from backend.api.observers import router as observers_router
from backend.api.loop import router as loop_router

settings = get_settings()


def seed_agents(db):
    """Insert pre-populated agents if not already in DB."""
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
    from backend.agents.tier2.validator import apex_val
    from backend.agents.tier2.anomaly import apex_anom
    from backend.agents.tier3.learner import paddock_1, paddock_2, paddock_3

    default_agents = [
        oracle, vector, podium, falcon, sigma, circuit,
        regs, storm, ledger, rival, pitwall, radar,
        apex_val, apex_anom, paddock_1, paddock_2, paddock_3,
    ]

    for agent in default_agents:
        existing = db.query(Agent).filter(Agent.name == agent.name).first()
        if not existing:
            row = Agent(
                name=agent.name,
                tier=agent.tier,
                domain=agent.domain,
                specialty=agent.specialty,
                model_id=agent.model_id,
                system_prompt=agent.system_prompt,
                bio=agent.bio,
                status="active",
                wins=0,
            )
            db.add(row)
    db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    db = SessionLocal()
    try:
        seed_agents(db)
        from backend.core.cascade import seed_knowledge_facts
        seed_knowledge_facts(db)
        from backend.core.news_feed import seed_news_events
        seed_news_events(db)
    finally:
        db.close()

    # Start autonomous agent loop
    from backend.core import autonomous_loop
    from backend.core.broadcaster import broadcast_to_debate

    async def _loop_broadcast(event: dict):
        await broadcast_to_debate(event.get("debate_id", 0), event)

    await autonomous_loop.start(_loop_broadcast)

    yield

    # Shutdown
    await autonomous_loop.stop()


app = FastAPI(
    title="Apex",
    description="Tiered AI Agent Knowledge Platform — Formula 1 Domain",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(agents_router)
app.include_router(debates_router)
app.include_router(knowledge_router)
app.include_router(award_router)
app.include_router(observers_router)
app.include_router(loop_router)


@app.get("/api/health")
def health():
    return {"status": "ok", "platform": "Apex", "domain": "f1"}


# Serve frontend
import os
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(os.path.join(frontend_dir, "static")):
    app.mount("/static", StaticFiles(directory=os.path.join(frontend_dir, "static")), name="static")


@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    index = os.path.join(frontend_dir, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    return {"detail": "Frontend not found"}
