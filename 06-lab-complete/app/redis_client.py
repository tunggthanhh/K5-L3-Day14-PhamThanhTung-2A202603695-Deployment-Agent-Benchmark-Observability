"""Lazy Redis client; importing the web app never requires Redis to be online."""
import redis

from app.config import settings

r = redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=1,
                   socket_timeout=1, health_check_interval=15)


def redis_healthy() -> bool:
    try:
        return bool(r.ping())
    except redis.RedisError:
        return False
