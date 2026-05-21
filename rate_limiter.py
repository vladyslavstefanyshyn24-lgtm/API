import time
from typing import Optional, Any

from fastapi import Request, HTTPException, status

# ---------------------------------------------------------------------------
# Redis client (module-level singleton, replaced in tests via dependency override)
# ---------------------------------------------------------------------------

redis_client: Optional[Any] = None


def get_redis() -> Any:
    """Return the module-level Redis client (overridden in tests)."""
    return redis_client


# ---------------------------------------------------------------------------
# Limits config
# ---------------------------------------------------------------------------

RATE_LIMITS: dict[str, tuple[int, int]] = {
    "anonymous":     (2,  60),   # 2  requests / 60 s
    "authenticated": (10, 60),   # 10 requests / 60 s
}

# ---------------------------------------------------------------------------
# Sliding-window rate limiter
# ---------------------------------------------------------------------------


async def rate_limit(
    request: Request,
    user_id: Optional[str] = None,
    r: Optional[Any] = None,
) -> None:
    if r is None:
        r = get_redis()

    # If Redis is not running — fail loudly so it's obvious
    if r is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiter unavailable: Redis is not connected. Start Redis first.",
        )

    identity = user_id if user_id else request.client.host
    limit_type = "authenticated" if user_id else "anonymous"
    limit, period = RATE_LIMITS[limit_type]

    key = f"rate_limit:{identity}"
    now = int(time.time())
    window_start = now - period

    # 1. Drop entries older than the current window
    await r.zremrangebyscore(key, min=0, max=window_start)

    # 2. Count remaining entries in the window
    request_count = await r.zcard(key)

    # 3. Reject if limit reached
    if request_count >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
        )

    # 4. Record this request (unique member per request to handle same-second bursts)
    member = f"{now}:{request_count}"
    await r.zadd(key, {member: now})

    # 5. Reset TTL so the key expires naturally after one idle period
    await r.expire(key, period)
