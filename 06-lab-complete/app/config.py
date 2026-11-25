"""Application configuration loaded exclusively from environment variables."""
import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    port: int
    environment: str
    agent_api_key: str
    redis_url: str
    rate_limit_per_minute: int
    daily_budget_usd: float


settings = Settings(
    port=_int("PORT", 8000),
    environment=os.getenv("ENVIRONMENT", "development"),
    agent_api_key=os.getenv("AGENT_API_KEY", "dev-key"),
    redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    rate_limit_per_minute=max(1, _int("RATE_LIMIT_PER_MINUTE", 10)),
    daily_budget_usd=max(0.0, _float("DAILY_BUDGET_USD", _float("MONTHLY_BUDGET_USD", 10.0))),
)
