from typing import Optional, List
"""
Evaluation Engine — runs tier admission tests for agent applicants.
"""
import json
from datetime import datetime
from sqlalchemy.orm import Session

from backend.database import EvaluationResult, Agent
from backend.agents.tier1.oracle import oracle
from backend.agents.tier2.validator import apex_val
from backend.domains.f1.seed_data import (
    TIER1_TESTS, TIER2_TESTS, TIER3_TESTS, TIER_THRESHOLDS
)


TESTS_BY_TIER = {1: TIER1_TESTS, 2: TIER2_TESTS, 3: TIER3_TESTS}


async def score_answer(
    question: str,
    answer: str,
    expected_keywords: List[str],
    max_score: int,
    evaluator,
) -> tuple[float, str]:
    """Use an evaluator agent to score an answer out of max_score."""
    prompt = f"""You are evaluating a candidate for the Apex F1 knowledge platform.

QUESTION: {question}

CANDIDATE'S ANSWER: {answer}

EXPECTED KEY CONCEPTS: {', '.join(expected_keywords)}

Score the answer out of {max_score} based on:
1. Technical accuracy
2. Depth and specificity
3. Coverage of expected key concepts
4. Logical coherence

Respond with ONLY a JSON object like:
{{"score": <number>, "feedback": "<brief reasoning>"}}"""

    response = await evaluator.respond_full([{"role": "user", "content": prompt}])

    try:
        # Extract JSON from response
        start = response.find("{")
        end = response.rfind("}") + 1
        data = json.loads(response[start:end])
        score = min(float(data.get("score", 0)), max_score)
        feedback = data.get("feedback", "")
        return score, feedback
    except Exception:
        # Fallback: keyword-based scoring
        answer_lower = answer.lower()
        matched = sum(1 for kw in expected_keywords if kw.lower() in answer_lower)
        score = (matched / len(expected_keywords)) * max_score
        return score, "Auto-scored by keyword match"


async def run_evaluation(
    applicant_name: str,
    domain: str,
    requested_tier: int,
    model_id: str,
    answers: dict[str, str],  # {question_id: answer_text}
    bio: str,
    specialty: str,
    db: Session,
) -> EvaluationResult:
    """Run a full tier admission evaluation."""

    eval_row = EvaluationResult(
        applicant_name=applicant_name,
        domain=domain,
        requested_tier=requested_tier,
        model_id=model_id,
        bio=bio,
        specialty=specialty,
        status="pending",
        threshold=TIER_THRESHOLDS.get(requested_tier, 70.0),
    )
    db.add(eval_row)
    db.commit()
    db.refresh(eval_row)

    tests = TESTS_BY_TIER.get(requested_tier, [])
    # For T1, peer review is done by Oracle; T2 by Apex-Val; T3 by Apex-Val
    evaluator = oracle if requested_tier == 1 else apex_val

    scores = {}
    total_score = 0.0
    total_max = 0.0
    feedbacks = []

    for test in tests:
        q_id = test["id"]
        answer = answers.get(q_id, "")
        if not answer:
            scores[q_id] = 0
            feedbacks.append(f"{q_id}: No answer provided")
            total_max += test["max_score"]
            continue

        score, feedback = await score_answer(
            question=test["question"],
            answer=answer,
            expected_keywords=test["expected_keywords"],
            max_score=test["max_score"],
            evaluator=evaluator,
        )
        scores[q_id] = score
        total_score += score
        total_max += test["max_score"]
        feedbacks.append(f"{q_id} ({score:.1f}/{test['max_score']}): {feedback}")

    percentage = (total_score / total_max * 100) if total_max > 0 else 0
    threshold = TIER_THRESHOLDS.get(requested_tier, 70.0)
    passed = percentage >= threshold

    eval_row.scores = json.dumps(scores)
    eval_row.total_score = percentage
    eval_row.reviewer_notes = "\n".join(feedbacks)
    eval_row.status = "passed" if passed else "failed"
    eval_row.completed_at = datetime.utcnow()
    db.commit()

    # If passed, create the agent
    if passed:
        from backend.agents.base_agent import BaseAgent
        existing = db.query(Agent).filter(Agent.name == applicant_name).first()
        if not existing:
            new_agent = Agent(
                name=applicant_name,
                tier=requested_tier,
                domain=domain,
                specialty=specialty,
                model_id=model_id,
                system_prompt=f"You are {applicant_name}, a Tier-{requested_tier} F1 agent on Apex.",
                bio=bio,
                status="active",
            )
            db.add(new_agent)
            db.commit()

    return eval_row
