"""
Autonomous Agent Loop — perpetual AI discourse engine.

Agents continuously debate news events, conspiracy theories, technical
analyses, strategic puzzles, and theory follow-ups — like a Reddit/Twitter
feed powered entirely by AI agents.
"""
import asyncio
import logging
import random
from typing import Optional, Callable

logger = logging.getLogger(__name__)

# ── Loop state (module-level singleton) ────────────────────────────
_loop_running: bool = False
_loop_task: Optional[asyncio.Task] = None
_current_topic: Optional[str] = None
_current_category: Optional[str] = None
_debates_run: int = 0

COOLDOWN_SECONDS = 20  # gap between debates (debates themselves take several minutes)

# ── F1 universe constants ──────────────────────────────────────────
TEAMS = [
    "Red Bull", "Ferrari", "Mercedes", "McLaren", "Aston Martin",
    "Alpine", "Williams", "Haas", "Kick Sauber", "RB",
]
DRIVERS = [
    "Verstappen", "Norris", "Leclerc", "Hamilton", "Russell",
    "Piastri", "Sainz", "Alonso", "Pérez", "Bearman",
]
CIRCUITS = [
    "Monaco", "Silverstone", "Spa", "Monza", "Suzuka",
    "Singapore", "Austin", "Interlagos", "Bahrain", "Jeddah",
]

# ── Topic pools by category ────────────────────────────────────────
TOPICS: dict[str, list[str]] = {
    "conspiracy": [
        "Is {team} deliberately sandbagging in qualifying to protect race pace secrets?",
        "Are {team} running an illegal floor concept that passes FIA scrutineering on a technicality?",
        "Is the FIA selectively enforcing technical directives to disadvantage {team}?",
        "Has {team} found a grey area in the 2026 regulations worth 0.4 seconds per lap?",
        "Are Pirelli tyre compounds being optimised to favour {team}'s car characteristics?",
        "Is {driver} receiving preferential treatment from {team} at {rival}'s expense?",
        "Did {team} reverse-engineer {other}'s suspension concept after Abu Dhabi teardown?",
        "Is the budget cap being enforced fairly, or are {team} exploiting accounting loopholes?",
        "Are {team}'s pit stop times suspiciously fast due to pre-positioned equipment?",
        "Is {driver} secretly preparing a move to {other} that management are covering up?",
        "Has {team} been sharing CFD data with customer teams in violation of commercial rights?",
        "Are FIA weight checks being gamed by {team} using ballast removal after qualifying?",
        "Is {team}'s supposed reliability problem actually deliberate to hide true engine power?",
        "Are crash tests at {team} being manipulated to allow flexing chassis beyond regulations?",
    ],
    "technical": [
        "Will {team}'s upcoming floor revision deliver the 0.3s improvement they desperately need?",
        "How does {team}'s beam wing concept affect rear diffuser performance in slow-speed corners?",
        "Is the zero-pod concept dead, or will it return under 2026 active aero regulations?",
        "What is the optimal DRS train strategy given current aerodynamic turbulence wake profiles?",
        "How does tyre thermal management differ between {team}'s high vs low downforce setups?",
        "Is ground-effect porpoising returning under 2026 regulations at street circuits?",
        "Can {team}'s power unit close the thermal efficiency gap to the benchmark by season end?",
        "Are flexible front wing endplates within current deflection tests providing meaningful laptime?",
        "What is the development ROI of a B-spec car versus continuous incremental upgrades for {team}?",
        "How does {circuit}'s surface evolution affect optimal compound selection across the weekend?",
        "Is {team}'s new suspension geometry a genuine correlation between CFD and real-world performance?",
        "What upgrade philosophy should {team} adopt when they are 0.8 seconds off the pace leaders?",
        "How does {team}'s cooling concept at high-temperature circuits like {circuit} affect downforce?",
        "Is the mini-DRS concept on {team}'s rear wing within the spirit of the regulations?",
    ],
    "strategy": [
        "Should {team} sacrifice {driver}'s race result for constructors' championship position?",
        "Is the undercut still the dominant strategy at {circuit} with current compound degradation?",
        "How should a midfield team approach a split 2-stop vs 3-stop strategy at {circuit}?",
        "Is the Virtual Safety Car deployed too conservatively, artificially distorting race outcomes?",
        "Should {team} prioritise qualifying pace or race pace setup philosophy this season?",
        "At what championship points deficit should {team} switch entirely to next-season development?",
        "Is {driver}'s superior tyre management worth the qualifying pace deficit to {rival}?",
        "Does the sprint race format fundamentally distort the optimal tyre allocation strategy?",
        "Should {driver} adopt a defensive 1-stop strategy at {circuit} or attack and control the race?",
        "Is a 1-stop strategy viable at {circuit} given current safety car probability statistics?",
        "How does the threat of rain at {circuit} change {team}'s strategic decision tree?",
        "Should {team} use {driver} as a 'roadblock' to protect {rival}'s championship lead?",
    ],
    "historical": [
        "Was {driver}'s title campaign more dominant than Schumacher's 2004 season?",
        "Did the 2026 technical reset genuinely level the field or just slow the top teams?",
        "Is {team}'s current development trajectory comparable to Mercedes' 2014–2020 dominance run?",
        "How does the current {driver} vs {rival} rivalry compare to Senna vs Prost historically?",
        "Was introducing DRS the right call for overtaking, or has it cheapened on-track passes?",
        "Has the budget cap fundamentally changed the competitive order or just slowed spending?",
        "Is {circuit} still the most challenging circuit on the calendar compared to the 1980s era?",
        "Was the V10 era's raw power more spectacular than the current hybrid-turbo formula?",
    ],
    "prediction": [
        "Based on current trajectories, who wins the Drivers' Championship and why?",
        "Which team will make the biggest performance leap in the second half of the season?",
        "Will {team} have secured a top-3 constructor position by the end of the season?",
        "Is {driver} going to win at {circuit} this season given their track record?",
        "Which mid-field team is most likely to score a shock podium at {circuit}?",
        "Will {team}'s development rate be enough to challenge the frontrunners by the final race?",
        "Is {driver} the future world champion, or will the next title go to {rival}?",
        "Which team faces the greatest risk of falling from the top 5 constructors by season end?",
    ],
}


def _fill(template: str) -> str:
    team = random.choice(TEAMS)
    other = random.choice([t for t in TEAMS if t != team])
    driver = random.choice(DRIVERS)
    rival = random.choice([d for d in DRIVERS if d != driver])
    circuit = random.choice(CIRCUITS)
    return template.format(
        team=team, other=other, driver=driver, rival=rival, circuit=circuit,
    )


def _random_topic() -> tuple[str, str]:
    """Return (topic, category). Weights favour conspiracy + technical."""
    weights = {"conspiracy": 25, "technical": 25, "strategy": 20,
               "historical": 15, "prediction": 15}
    category = random.choices(list(weights.keys()), weights=list(weights.values()), k=1)[0]
    topic = _fill(random.choice(TOPICS[category]))
    return topic, category


def _news_topic(db) -> tuple[Optional[str], Optional[object], str]:
    from backend.core.news_feed import get_latest_unprocessed
    events = get_latest_unprocessed(db, "f1", limit=1)
    if events:
        e = events[0]
        return f"Breaking: {e.headline}\n\nContext: {e.content[:400]}", e, "breaking"
    return None, None, ""


# ── Public API ─────────────────────────────────────────────────────

def get_status() -> dict:
    return {
        "running": _loop_running,
        "debates_run": _debates_run,
        "current_topic": _current_topic,
        "current_category": _current_category,
    }


async def start(broadcast_fn: Optional[Callable] = None):
    global _loop_task, _loop_running
    if _loop_running:
        return
    _loop_running = True
    _loop_task = asyncio.create_task(_loop_body(broadcast_fn))
    logger.info("Autonomous loop started")


async def stop():
    global _loop_running, _loop_task
    _loop_running = False
    if _loop_task:
        _loop_task.cancel()
        try:
            await _loop_task
        except asyncio.CancelledError:
            pass
        _loop_task = None
    logger.info("Autonomous loop stopped")


# ── Private loop body ──────────────────────────────────────────────

async def _loop_body(broadcast_fn: Optional[Callable] = None):
    global _current_topic, _current_category, _debates_run, _loop_running

    from backend.database import SessionLocal, Theory
    from backend.core.debate_engine import run_debate
    from backend.core.cascade import run_anomaly_scan, validate_theory
    from backend.core.broadcaster import broadcast_global

    scan_counter = 0

    while _loop_running:
        db = SessionLocal()
        try:
            # 35% news, 65% spontaneous
            topic, news_event, category = None, None, ""
            if random.random() < 0.35:
                topic, news_event, category = _news_topic(db)
            if not topic:
                topic, category = _random_topic()

            _current_topic = topic[:120]
            _current_category = category

            # Announce to feed
            await broadcast_global({
                "type": "loop_status",
                "status": "debating",
                "topic": _current_topic,
                "category": category,
                "debates_run": _debates_run,
            })

            logger.info(f"[loop] #{_debates_run + 1} [{category}] {topic[:70]}")

            await run_debate(
                topic=topic,
                db=db,
                news_event=news_event,
                broadcast=broadcast_fn,
            )
            _debates_run += 1

            # Every 4 debates → anomaly scan
            scan_counter += 1
            if scan_counter % 4 == 0:
                logger.info("[loop] Running anomaly scan")
                try:
                    await run_anomaly_scan(db)
                except Exception as e:
                    logger.warning(f"[loop] Anomaly scan error: {e}")

            # Validate up to 3 pending theories
            pending = db.query(Theory).filter(Theory.status == "pending").limit(3).all()
            for t in pending:
                try:
                    await validate_theory(t.id, db)
                except Exception as e:
                    logger.warning(f"[loop] Theory {t.id} validation failed: {e}")

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[loop] Error: {e}", exc_info=True)
        finally:
            db.close()
            _current_topic = None
            _current_category = None

        if _loop_running:
            await broadcast_global({
                "type": "loop_status",
                "status": "cooldown",
                "debates_run": _debates_run,
                "cooldown_seconds": COOLDOWN_SECONDS,
            })
            try:
                await asyncio.sleep(COOLDOWN_SECONDS)
            except asyncio.CancelledError:
                break

    _loop_running = False
    logger.info("[loop] Exited")
