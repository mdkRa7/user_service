from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from .config import settings


def get_client_ip(request: Request) -> str:
    """Return the real client IP behind a reverse proxy.

    Vercel/Northflank/Cloudflare overwrite X-Forwarded-For. Only trust this
    header when the app is not directly exposed to the internet.
    """
    for header in ("cf-connecting-ip", "x-real-ip"):
        value = request.headers.get(header)
        if value:
            return value.strip()

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return get_remote_address(request)


# Redis-backed storage makes limits shared between workers and survives
# restarts (the default in-memory storage is per-process).
limiter = Limiter(
    key_func=get_client_ip,
    storage_uri=str(settings.redis.url),
)
