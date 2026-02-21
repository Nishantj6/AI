from typing import Optional, List
"""
Apex Award — Nobel-style annual prediction award.
T1 agents make season-opening predictions; at season end,
the most accurate predictor wins the Apex Award.
"""
import json
from datetime import datetime
from sqlalchemy.orm import Session

from backend.database import ApexPrediction, Agent
from backend.agents.tier1.oracle import oracle
from backend.agents.tier1.vector import vector
from backend.agents.tier1.podium import podium
from backend.core.news_feed import get_recent_events


AWARD_AGENTS = [oracle, vector, podium]
CURRENT_SEASON = "2025"


async def generate_season_predictions(db: Session) -> list[ApexPrediction]:
    """Ask each T1 agent to generate a season prediction for the Apex Award."""
    events = get_recent_events(db, "f1", limit=10)
    news_context = "\n".join(f"- {e.headline}" for e in events[:5])

    prompt = (
        f"You are making your grand prediction for the {CURRENT_SEASON} F1 season for the Apex Award.\n\n"
        f"Recent news context:\n{news_context}\n\n"
        f"Make ONE bold, specific, falsifiable prediction about the {CURRENT_SEASON} F1 season. "
        f"It should be something that can be definitively proven right or wrong by season end.\n\n"
        f"Format: State your prediction clearly in 2-3 sentences, then explain your reasoning in 2-3 sentences."
    )

    predictions = []
    for agent in AWARD_AGENTS:
        # Check if this agent already has a prediction this season
        db_agent = db.query(Agent).filter(Agent.name == agent.name).first()
        if not db_agent:
            continue

        existing = (
            db.query(ApexPrediction)
            .filter(
                ApexPrediction.agent_id == db_agent.id,
                ApexPrediction.season == CURRENT_SEASON,
            )
            .first()
        )
        if existing:
            predictions.append(existing)
            continue

        response = await agent.respond_full([{"role": "user", "content": prompt}])

        pred = ApexPrediction(
            agent_id=db_agent.id,
            claim=response,
            domain="f1",
            season=CURRENT_SEASON,
            status="pending",
        )
        db.add(pred)
        db.commit()
        db.refresh(pred)
        predictions.append(pred)

    return predictions


async def validate_predictions_against_news(db: Session) -> List[dict]:
    """
    Compare pending predictions against recent news events.
    Use Oracle to assess accuracy.
    """
    pending = (
        db.query(ApexPrediction)
        .filter(ApexPrediction.status == "pending", ApexPrediction.season == CURRENT_SEASON)
        .all()
    )
    if not pending:
        return []

    events = get_recent_events(db, "f1", limit=15)
    news_text = "\n".join(f"- {e.headline}: {e.content[:200]}" for e in events)

    results = []
    for pred in pending:
        agent_row = db.query(Agent).filter(Agent.id == pred.agent_id).first()
        agent_name = agent_row.name if agent_row else "Unknown"

        validation_prompt = (
            f"Assess whether this F1 prediction has come true based on recent news.\n\n"
            f"PREDICTION by {agent_name}:\n{pred.claim}\n\n"
            f"RECENT NEWS:\n{news_text}\n\n"
            f"Has this prediction come true? Reply with JSON only:\n"
            f'{{"verdict": "true"|"false"|"pending", "confidence": 0.0-1.0, "reasoning": "..."}}'
        )

        response = await oracle.respond_full([{"role": "user", "content": validation_prompt}])

        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            data = json.loads(response[start:end])
            verdict = data.get("verdict", "pending")
            confidence = float(data.get("confidence", 0.5))
            reasoning = data.get("reasoning", "")
        except Exception:
            verdict = "pending"
            confidence = 0.5
            reasoning = "Parse error"

        if verdict in ("true", "false"):
            pred.status = verdict
            pred.accuracy_score = confidence if verdict == "true" else (1 - confidence)
            pred.validation_date = datetime.utcnow()
            pred.validation_source = reasoning[:500]
            db.commit()

        results.append({
            "prediction_id": pred.id,
            "agent": agent_name,
            "claim": pred.claim[:200],
            "verdict": verdict,
            "confidence": confidence,
            "reasoning": reasoning,
        })

    return results


def get_award_leaderboard(db: Session) -> List[dict]:
    """Return ranked leaderboard of all seasons' predictions."""
    predictions = (
        db.query(ApexPrediction)
        .filter(ApexPrediction.status.in_(["true", "false"]))
        .all()
    )

    # Aggregate by agent
    agent_scores: dict[int, dict] = {}
    for pred in predictions:
        aid = pred.agent_id
        if aid not in agent_scores:
            agent_row = db.query(Agent).filter(Agent.id == aid).first()
            agent_scores[aid] = {
                "agent_id": aid,
                "agent_name": agent_row.name if agent_row else "Unknown",
                "total_predictions": 0,
                "correct": 0,
                "accuracy": 0.0,
                "apex_awards": agent_row.wins if agent_row else 0,
            }
        agent_scores[aid]["total_predictions"] += 1
        if pred.status == "true":
            agent_scores[aid]["correct"] += 1

    for data in agent_scores.values():
        total = data["total_predictions"]
        data["accuracy"] = round(data["correct"] / total, 3) if total > 0 else 0.0

    return sorted(agent_scores.values(), key=lambda x: x["accuracy"], reverse=True)


async def award_season_winner(season: str, db: Session) -> Optional[dict]:
    """Award the season's Apex Award to the most accurate predictor."""
    preds = (
        db.query(ApexPrediction)
        .filter(ApexPrediction.season == season, ApexPrediction.status.in_(["true", "false"]))
        .all()
    )
    if not preds:
        return None

    # Score: correct predictions weighted by confidence
    scores: dict[int, float] = {}
    for pred in preds:
        aid = pred.agent_id
        scores[aid] = scores.get(aid, 0.0) + (pred.accuracy_score or 0.0)

    if not scores:
        return None

    winner_id = max(scores, key=lambda k: scores[k])
    winner_agent = db.query(Agent).filter(Agent.id == winner_id).first()
    if winner_agent:
        winner_agent.wins += 1
        db.commit()

    return {
        "season": season,
        "winner": winner_agent.name if winner_agent else "Unknown",
        "score": round(scores[winner_id], 3),
        "all_scores": {
            db.query(Agent).filter(Agent.id == k).first().name: round(v, 3)
            for k, v in scores.items()
        },
    }
