import httpx

from .config import settings
from .exceptions import CaptchaError


async def verify_turnstile(token: str | None, remote_ip: str | None = None) -> None:
    """Verify a Cloudflare Turnstile token when CAPTCHA is enabled.

    If TURNSTILE_ENABLED is false (default), this is a no-op so local tests and
    the one-day demo do not depend on Cloudflare keys.
    """
    if not settings.turnstile.enabled:
        return
    if not token:
        raise CaptchaError()
    if not settings.turnstile.secret:
        raise CaptchaError("Captcha is not configured")

    payload = {
        "secret": settings.turnstile.secret,
        "response": token,
    }
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.post(settings.turnstile.verify_url, data=payload)
        result = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise CaptchaError("Captcha verification is unavailable") from exc

    if response.status_code != 200 or not result.get("success"):
        raise CaptchaError()
