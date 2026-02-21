from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import ApexPrediction, Agent, get_db
from backend.core.apex_award import (
    generate_season_predictions,
    validate_predictions_against_news,
    get_award_leaderboard,
    award_season_winner,
    CURRENT_SEASON,
)

router = APIRouter(prefix="/api/award", tags=["award"])


@router.get("")
def award_overview(db: Session = Depends(get_db)):
    leaderboard = get_award_leaderboard(db)
    # Current season predictions
    predictions = (
        db.query(ApexPrediction)
        .filter(ApexPrediction.season == CURRENT_SEASON)
        .all()
    )
    agents_map = {a.id: a.name for a in db.query(Agent).all()}
    return {
        "current_season": CURRENT_SEASON,
        "leaderboard": leaderboard,
        "season_predictions": [
            {
                "id": p.id,
                "agent": agents_map.get(p.agent_id, "Unknown"),
                "claim": p.claim,
                "status": p.status,
                "accuracy_score": p.accuracy_score,
                "prediction_date": p.prediction_date.isoformat(),
                "validation_date": p.validation_date.isoformat() if p.validation_date else None,
                "validation_source": p.validation_source,
            }
            for p in predictions
        ],
    }


@router.post("/generate-predictions")
async def generate_predictions(db: Session = Depends(get_db)):
    """Ask all T1 agents to submit their season prediction."""
    predictions = await generate_season_predictions(db)
    agents_map = {a.id: a.name for a in db.query(Agent).all()}
    return {
        "message": f"Generated {len(predictions)} predictions for {CURRENT_SEASON}",
        "predictions": [
            {
                "agent": agents_map.get(p.agent_id, "Unknown"),
                "claim": p.claim[:300],
                "status": p.status,
            }
            for p in predictions
        ],
    }


@router.post("/validate")
async def validate_predictions(db: Session = Depends(get_db)):
    """Check pending predictions against recent news."""
    results = await validate_predictions_against_news(db)
    return {"validated": len(results), "results": results}


@router.post("/award-winner/{season}")
async def award_winner(season: str, db: Session = Depends(get_db)):
    """Award the Apex Award for a given season."""
    result = await award_season_winner(season, db)
    if not result:
        return {"message": "No validated predictions found for this season"}
    return result


@router.get("/history")
def award_history(db: Session = Depends(get_db)):
    """Return all past Apex Award winners."""
    winners = (
        db.query(Agent)
        .filter(Agent.wins > 0)
        .order_by(Agent.wins.desc())
        .all()
    )
    return [
        {"name": a.name, "tier": a.tier, "wins": a.wins, "specialty": a.specialty}
        for a in winners
    ]
