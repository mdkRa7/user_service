import uuid
from typing import Annotated

from api.dependencies import dep_get_auth_service, get_refresh_token
from api.utils import delete_cookies, set_cookies
from core import limiter, settings
from core.captcha import verify_turnstile
from domain.services import AuthService
from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from schemas import LoginSchema, UserSchemaAdd, UserSchemaRead, VerifyEmailSchema

router = APIRouter(
    prefix=settings.api_prefix.auth,
    tags=["Auth"],
)


@router.post("/register")
@limiter.limit(settings.limiter.register_limit)
async def register_user(
    request: Request,
    background_tasks: BackgroundTasks,
    user_data: UserSchemaAdd,
    service: Annotated[AuthService, Depends(dep_get_auth_service)],
):
    await verify_turnstile(
        user_data.turnstile_token,
        request.client.host if request.client else None,
    )
    # Verification OFF (no SMTP server): create the account right away.
    # The code flow below and the /verify-email endpoint stay in place and are
    # used as soon as CONFIG__AUTH__EMAIL_VERIFICATION=true.
    if not settings.auth.email_verification:
        await service.register_user_without_verification(user_data)
        return {
            "message": "Registered. Email verification is disabled, you can log in now",
            "verification_required": False,
        }
    # Verification ON: send a code by email, the account is created in /verify-email.
    demo_code = await service.register_user(user_data, background_tasks)
    if demo_code:
        return {
            "message": "Demo mode: email sending is skipped, use the code below",
            "demo_code": demo_code,
            "verification_required": True,
        }
    return {
        "message": "Confirmation code sent to email",
        "verification_required": True,
    }


@router.post("/login")
@limiter.limit(settings.limiter.login)
async def login_user(
    request: Request,  # it needs only for limiter
    user_data: LoginSchema,
    response: Response,
    service: Annotated[AuthService, Depends(dep_get_auth_service)],
):
    obj = await service.login_user(user_data)
    set_cookies(response, obj.id, obj.role)
    return {"detail": "Logged in successfully"}


# Second step of registration, used only when CONFIG__AUTH__EMAIL_VERIFICATION=true.
# With verification disabled nobody calls it (there is no pending code).
@router.post("/verify-email", response_model=UserSchemaRead)
@limiter.limit(settings.limiter.verify_limit)
async def verify_email(
    request: Request,
    verify_data: VerifyEmailSchema,
    service: Annotated[AuthService, Depends(dep_get_auth_service)],
):
    return await service.verify_email(verify_data)


@router.post("/logout")
async def logout(response: Response):
    delete_cookies(response)
    return {"message": "Logged out successfully"}


@router.post("/refresh")
async def refresh(
    response: Response,
    refresh_token: Annotated[str, Depends(get_refresh_token)],
    service: Annotated[AuthService, Depends(dep_get_auth_service)],
):
    user = await service.refresh(refresh_token)
    set_cookies(response, user.id, user.role)
    return {"message": "Token successfully refreshed"}
