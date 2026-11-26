import uuid

from core import jwt_creator, limiter, settings
from domain.enums import Role
from fastapi import FastAPI, Response
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded


def register_limiter_handler(app: FastAPI) -> None:
    app.state.limiter = limiter
    app.add_exception_handler(
        RateLimitExceeded,
        _rate_limit_exceeded_handler,
    )


def delete_cookies(response: Response) -> None:
    for key in ("access_token", "refresh_token"):
        response.delete_cookie(
            key=key,
            path="/",
            domain=settings.cookie.domain,
            secure=settings.cookie.secure,
            httponly=True,
            samesite=settings.cookie.samesite,
        )


def set_cookies(response: Response, user_id: uuid.UUID, role: Role) -> None:
    response.set_cookie(
        key="access_token",
        value=jwt_creator.create_access_token(user_id, role),
        httponly=True,
        secure=settings.cookie.secure,
        samesite=settings.cookie.samesite,
        domain=settings.cookie.domain,
        path="/",
        max_age=settings.jwt.access_exp * 60,
    )

    response.set_cookie(
        key="refresh_token",
        value=jwt_creator.create_refresh_token(user_id, role),
        httponly=True,
        secure=settings.cookie.secure,
        samesite=settings.cookie.samesite,
        domain=settings.cookie.domain,
        path="/",
        max_age=settings.jwt.refresh_exp * 24 * 60 * 60,
    )
