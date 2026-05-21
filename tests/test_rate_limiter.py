"""
Unit tests for the sliding-window rate limiter.

Redis is replaced with an AsyncMock so no real Redis instance is needed.
FastAPI / starlette are stubbed before import so pydantic_core is never loaded
(the venv in this repo is Windows-only and won't run on Linux).

Test matrix
-----------
Anonymous user
  1. under limit  → passes (no exception)
  2. at/over limit → raises HTTP 429

Authenticated user
  1. under limit  → passes (no exception)
  2. at/over limit → raises HTTP 429
"""

import sys
import os
import types

# ---------------------------------------------------------------------------
# Stub out FastAPI / starlette BEFORE any project import so we never hit
# pydantic_core (a Windows-compiled binary that won't load on Linux).
# ---------------------------------------------------------------------------

def _make_http_exception():
    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str = ""):
            self.status_code = status_code
            self.detail = detail
            super().__init__(detail)
    return HTTPException

_HTTPException = _make_http_exception()

# Build minimal fake modules
_starlette = types.ModuleType("starlette")
_starlette_status = types.ModuleType("starlette.status")
_starlette_status.HTTP_429_TOO_MANY_REQUESTS = 429
_starlette.status = _starlette_status

_fastapi = types.ModuleType("fastapi")
_fastapi.HTTPException = _HTTPException
_fastapi.status = _starlette_status

# Stub Request as a simple passthrough
class _Request:
    pass

_fastapi.Request = _Request

sys.modules.setdefault("starlette", _starlette)
sys.modules.setdefault("starlette.status", _starlette_status)
sys.modules.setdefault("fastapi", _fastapi)

# ---------------------------------------------------------------------------
# Now safe to import project code
# ---------------------------------------------------------------------------

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import AsyncMock, MagicMock

from rate_limiter import rate_limit, RATE_LIMITS

HTTPException = _HTTPException   # alias for assertions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_request(host: str = "127.0.0.1") -> MagicMock:
    """Build a minimal fake Request object."""
    request = MagicMock()
    request.client = MagicMock()
    request.client.host = host
    return request


def _make_redis(*, current_count: int) -> AsyncMock:
    """
    Return a mock Redis client whose zcard() reports *current_count* existing
    entries (i.e. how many requests have already been made in this window).
    """
    r = AsyncMock()
    r.zremrangebyscore = AsyncMock(return_value=0)
    r.zcard = AsyncMock(return_value=current_count)
    r.zadd = AsyncMock(return_value=1)
    r.expire = AsyncMock(return_value=True)
    return r


# ---------------------------------------------------------------------------
# Anonymous user tests
# ---------------------------------------------------------------------------

class TestAnonymousRateLimit:
    """rate_limit() called without a user_id → anonymous limits apply (2 / min)."""

    LIMIT, _ = RATE_LIMITS["anonymous"]  # 2

    @pytest.mark.asyncio
    async def test_under_limit_passes(self):
        """First request by an anonymous user (count = 0 < 2) → no exception."""
        request = _make_request(host="192.168.1.1")
        mock_redis = _make_redis(current_count=0)

        await rate_limit(request, user_id=None, r=mock_redis)

        mock_redis.zadd.assert_awaited_once()
        mock_redis.expire.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_at_limit_raises_429(self):
        """Anonymous user has already used all 2 slots → HTTP 429."""
        request = _make_request(host="192.168.1.1")
        mock_redis = _make_redis(current_count=self.LIMIT)

        with pytest.raises(HTTPException) as exc_info:
            await rate_limit(request, user_id=None, r=mock_redis)

        assert exc_info.value.status_code == 429
        mock_redis.zadd.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_over_limit_raises_429(self):
        """Anonymous user exceeds the limit (e.g. via race) → HTTP 429."""
        request = _make_request(host="10.0.0.5")
        mock_redis = _make_redis(current_count=self.LIMIT + 5)

        with pytest.raises(HTTPException) as exc_info:
            await rate_limit(request, user_id=None, r=mock_redis)

        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_just_under_limit_passes(self):
        """One slot still available (count = limit - 1) → passes."""
        request = _make_request(host="10.0.0.5")
        mock_redis = _make_redis(current_count=self.LIMIT - 1)

        await rate_limit(request, user_id=None, r=mock_redis)

        mock_redis.zadd.assert_awaited_once()


# ---------------------------------------------------------------------------
# Authenticated user tests
# ---------------------------------------------------------------------------

class TestAuthenticatedRateLimit:
    """rate_limit() called with a user_id → authenticated limits apply (10 / min)."""

    LIMIT, _ = RATE_LIMITS["authenticated"]  # 10

    @pytest.mark.asyncio
    async def test_under_limit_passes(self):
        """Authenticated user: first request (count = 0 < 10) → no exception."""
        request = _make_request()
        mock_redis = _make_redis(current_count=0)

        await rate_limit(request, user_id="user-abc-123", r=mock_redis)

        mock_redis.zadd.assert_awaited_once()
        mock_redis.expire.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_at_limit_raises_429(self):
        """Authenticated user has used all 10 slots → HTTP 429."""
        request = _make_request()
        mock_redis = _make_redis(current_count=self.LIMIT)

        with pytest.raises(HTTPException) as exc_info:
            await rate_limit(request, user_id="user-abc-123", r=mock_redis)

        assert exc_info.value.status_code == 429
        mock_redis.zadd.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_over_limit_raises_429(self):
        """Authenticated user well over limit → HTTP 429."""
        request = _make_request()
        mock_redis = _make_redis(current_count=self.LIMIT + 10)

        with pytest.raises(HTTPException) as exc_info:
            await rate_limit(request, user_id="power-user", r=mock_redis)

        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_just_under_limit_passes(self):
        """One slot still available (count = 9 of 10) → passes."""
        request = _make_request()
        mock_redis = _make_redis(current_count=self.LIMIT - 1)

        await rate_limit(request, user_id="user-abc-123", r=mock_redis)

        mock_redis.zadd.assert_awaited_once()

    # -----------------------------------------------------------------------
    # Extra: verify correct Redis key is used per identity
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_redis_key_uses_user_id_for_authenticated(self):
        """The Redis key must be based on user_id, not the client host."""
        request = _make_request(host="1.2.3.4")
        mock_redis = _make_redis(current_count=0)

        await rate_limit(request, user_id="unique-user-99", r=mock_redis)

        key_used = mock_redis.zremrangebyscore.call_args[0][0]
        assert "unique-user-99" in key_used
        assert "1.2.3.4" not in key_used

    @pytest.mark.asyncio
    async def test_redis_key_uses_host_for_anonymous(self):
        """The Redis key must be based on the client host for anonymous users."""
        request = _make_request(host="5.6.7.8")
        mock_redis = _make_redis(current_count=0)

        await rate_limit(request, user_id=None, r=mock_redis)

        key_used = mock_redis.zremrangebyscore.call_args[0][0]
        assert "5.6.7.8" in key_used

    # -----------------------------------------------------------------------
    # Extra: stale entries are cleaned before counting
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_stale_entries_removed_before_count(self):
        """zremrangebyscore must be called before zcard on every request."""
        request = _make_request()
        mock_redis = _make_redis(current_count=0)
        call_order: list[str] = []

        async def track_zremrangebyscore(*a, **kw):
            call_order.append("zremrangebyscore")
            return 0

        async def track_zcard(*a, **kw):
            call_order.append("zcard")
            return 0

        mock_redis.zremrangebyscore = AsyncMock(side_effect=track_zremrangebyscore)
        mock_redis.zcard = AsyncMock(side_effect=track_zcard)

        await rate_limit(request, user_id="u1", r=mock_redis)

        assert call_order.index("zremrangebyscore") < call_order.index("zcard")



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_request(host: str = "127.0.0.1") -> MagicMock:
    """Build a minimal fake Request object."""
    request = MagicMock()
    request.client = MagicMock()
    request.client.host = host
    return request


def _make_redis(*, current_count: int) -> AsyncMock:
    """
    Return a mock Redis client whose zcard() reports *current_count* existing
    entries (i.e. how many requests have already been made in this window).
    """
    r = AsyncMock()
    r.zremrangebyscore = AsyncMock(return_value=0)
    r.zcard = AsyncMock(return_value=current_count)
    r.zadd = AsyncMock(return_value=1)
    r.expire = AsyncMock(return_value=True)
    return r


# ---------------------------------------------------------------------------
# Anonymous user tests
# ---------------------------------------------------------------------------

class TestAnonymousRateLimit:
    """rate_limit() called without a user_id → anonymous limits apply (2 / min)."""

    LIMIT, _ = RATE_LIMITS["anonymous"]  # 2

    @pytest.mark.asyncio
    async def test_under_limit_passes(self):
        """First request by an anonymous user (count = 0 < 2) → no exception."""
        request = _make_request(host="192.168.1.1")
        mock_redis = _make_redis(current_count=0)

        # Should complete without raising
        await rate_limit(request, user_id=None, r=mock_redis)

        # Verify the request was recorded
        mock_redis.zadd.assert_awaited_once()
        mock_redis.expire.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_at_limit_raises_429(self):
        """Anonymous user has already used all 2 slots → HTTP 429."""
        request = _make_request(host="192.168.1.1")
        mock_redis = _make_redis(current_count=self.LIMIT)  # count == limit

        with pytest.raises(HTTPException) as exc_info:
            await rate_limit(request, user_id=None, r=mock_redis)

        assert exc_info.value.status_code == 429
        # No new request should have been recorded
        mock_redis.zadd.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_over_limit_raises_429(self):
        """Anonymous user exceeds the limit (e.g. via race) → HTTP 429."""
        request = _make_request(host="10.0.0.5")
        mock_redis = _make_redis(current_count=self.LIMIT + 5)

        with pytest.raises(HTTPException) as exc_info:
            await rate_limit(request, user_id=None, r=mock_redis)

        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_just_under_limit_passes(self):
        """One slot still available (count = limit - 1) → passes."""
        request = _make_request(host="10.0.0.5")
        mock_redis = _make_redis(current_count=self.LIMIT - 1)

        await rate_limit(request, user_id=None, r=mock_redis)  # must not raise

        mock_redis.zadd.assert_awaited_once()


# ---------------------------------------------------------------------------
# Authenticated user tests
# ---------------------------------------------------------------------------

class TestAuthenticatedRateLimit:
    """rate_limit() called with a user_id → authenticated limits apply (10 / min)."""

    LIMIT, _ = RATE_LIMITS["authenticated"]  # 10

    @pytest.mark.asyncio
    async def test_under_limit_passes(self):
        """Authenticated user: first request (count = 0 < 10) → no exception."""
        request = _make_request()
        mock_redis = _make_redis(current_count=0)

        await rate_limit(request, user_id="user-abc-123", r=mock_redis)

        mock_redis.zadd.assert_awaited_once()
        mock_redis.expire.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_at_limit_raises_429(self):
        """Authenticated user has used all 10 slots → HTTP 429."""
        request = _make_request()
        mock_redis = _make_redis(current_count=self.LIMIT)

        with pytest.raises(HTTPException) as exc_info:
            await rate_limit(request, user_id="user-abc-123", r=mock_redis)

        assert exc_info.value.status_code == 429
        mock_redis.zadd.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_over_limit_raises_429(self):
        """Authenticated user well over limit → HTTP 429."""
        request = _make_request()
        mock_redis = _make_redis(current_count=self.LIMIT + 10)

        with pytest.raises(HTTPException) as exc_info:
            await rate_limit(request, user_id="power-user", r=mock_redis)

        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_just_under_limit_passes(self):
        """One slot still available (count = 9 of 10) → passes."""
        request = _make_request()
        mock_redis = _make_redis(current_count=self.LIMIT - 1)

        await rate_limit(request, user_id="user-abc-123", r=mock_redis)

        mock_redis.zadd.assert_awaited_once()

    # -----------------------------------------------------------------------
    # Extra: verify correct Redis key is used per identity
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_redis_key_uses_user_id_for_authenticated(self):
        """The Redis key must be based on user_id, not the client host."""
        request = _make_request(host="1.2.3.4")
        mock_redis = _make_redis(current_count=0)

        await rate_limit(request, user_id="unique-user-99", r=mock_redis)

        # zremrangebyscore is called with the key first
        key_used = mock_redis.zremrangebyscore.call_args[0][0]
        assert "unique-user-99" in key_used
        assert "1.2.3.4" not in key_used

    @pytest.mark.asyncio
    async def test_redis_key_uses_host_for_anonymous(self):
        """The Redis key must be based on the client host for anonymous users."""
        request = _make_request(host="5.6.7.8")
        mock_redis = _make_redis(current_count=0)

        await rate_limit(request, user_id=None, r=mock_redis)

        key_used = mock_redis.zremrangebyscore.call_args[0][0]
        assert "5.6.7.8" in key_used

    # -----------------------------------------------------------------------
    # Extra: stale entries are cleaned before counting
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_stale_entries_removed_before_count(self):
        """zremrangebyscore must be called before zcard on every request."""
        request = _make_request()
        mock_redis = _make_redis(current_count=0)
        call_order: list[str] = []

        async def track_zremrangebyscore(*a, **kw):
            call_order.append("zremrangebyscore")
            return 0

        async def track_zcard(*a, **kw):
            call_order.append("zcard")
            return 0

        mock_redis.zremrangebyscore = AsyncMock(side_effect=track_zremrangebyscore)
        mock_redis.zcard = AsyncMock(side_effect=track_zcard)

        await rate_limit(request, user_id="u1", r=mock_redis)

        assert call_order.index("zremrangebyscore") < call_order.index("zcard")
