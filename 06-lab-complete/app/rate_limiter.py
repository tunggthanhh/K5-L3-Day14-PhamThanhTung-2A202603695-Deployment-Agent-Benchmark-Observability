"""Redis-backed, atomic sliding-window API-key rate limit."""
import time

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

_RATE_LIMIT_LUA = """
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local maximum = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, now - window)
local used = redis.call('ZCARD', KEYS[1])
if used >= maximum then
  local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
  return {0, oldest[2] or now}
end
redis.call('ZADD', KEYS[1], now, ARGV[4])
redis.call('EXPIRE', KEYS[1], math.ceil(window / 1000))
return {1, 0}
"""


def check_rate_limit(key: str) -> None:
    now_ms = int(time.time() * 1000)
    try:
        allowed, oldest = r.eval(_RATE_LIMIT_LUA, 1, f"rate-limit:{key}", now_ms, 60_000,
                                 settings.rate_limit_per_minute, f"{now_ms}:{time.time_ns()}")
    except redis.RedisError:
        raise HTTPException(status_code=503, detail="Rate limiter is temporarily unavailable")
    if not int(allowed):
        retry_after = max(1, int((int(oldest) + 60_000 - now_ms + 999) / 1000))
        raise HTTPException(status_code=429, detail="Rate limit exceeded",
                            headers={"Retry-After": str(retry_after)})
