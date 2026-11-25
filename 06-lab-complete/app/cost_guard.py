"""Daily LLM budget guard persisted in Redis."""
from datetime import UTC, datetime

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def _budget_key() -> str:
    return f"agent-cost:{datetime.now(UTC).date().isoformat()}"


def check_budget() -> None:
    try:
        spent = float(r.get(_budget_key()) or 0.0)
    except redis.RedisError:
        raise HTTPException(status_code=503, detail="Cost guard is temporarily unavailable")
    if spent >= settings.daily_budget_usd:
        raise HTTPException(status_code=402, detail="Daily LLM budget exhausted")


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Persist a request's estimated USD cost and return it."""
    cost = input_tokens / 1000 * PRICE_INPUT_PER_1K + output_tokens / 1000 * PRICE_OUTPUT_PER_1K
    try:
        pipe = r.pipeline()
        pipe.incrbyfloat(_budget_key(), cost)
        pipe.expire(_budget_key(), 172800)
        pipe.execute()
    except redis.RedisError:
        raise HTTPException(status_code=503, detail="Cost guard is temporarily unavailable")
    return cost
