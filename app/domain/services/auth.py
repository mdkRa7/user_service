import hashlib
import json
import secrets
import time
import uuid
from datetime import datetime, timezone

from core import (
    EmailQuotaExceededError,
    IntegrityConstraintError,
    InvalidCodeError,
    InvalidCredentialsError,
    TokenValidationError,
    TooManyRequestsError,
    UserBlockedError,
    security,
    settings,
)
from infrastructure.clients import MailService
from infrastructure.database.crud.user import CRUDUser
from infrastructure.database.models import User
from redis.asyncio import Redis
from schemas import LoginSchema, UserSchemaAdd, VerifyEmailSchema


class AuthService:
    def __init__(self, *, crud: CRUDUser, mail: MailService, redis: Redis):
        self._crud = crud
        self._mail = mail
        self._redis = redis

    async def register_user(
        self, user_data: UserSchemaAdd, background_tasks
    ) -> str | None:
        """Create a pending registration.

        Returns a demo code only when the verification email is intentionally
        skipped (DEMO_MODE or the daily mail quota was exhausted and the
        fallback is enabled).
        """
        user_dict = user_data.model_dump(
            exclude={"password_confirm", "turnstile_token"}
        )
        email = str(user_dict["email"]).strip().lower()
        user_dict["email"] = email

        if await self._crud.get_by_email(email):
            raise IntegrityConstraintError()

        # One code per email per minute: stops re-registration spam and
        # prevents overwriting a code that is already in flight.
        cooldown_key = f"verify_email:cooldown:{email}"
        if not await self._redis.set(cooldown_key, 1, nx=True, ex=60):
            raise TooManyRequestsError(
                "A confirmation code was sent recently. Try again in a minute."
            )
        await self._redis.delete(f"verify_email:attempts:{email}")

        user_dict["password"] = security.hash_password(user_dict["password"])

        demo_code: str | None = None
        if settings.demo.enabled:
            code = settings.demo.code
            demo_code = code
        else:
            code = f"{secrets.randbelow(1_000_000):06d}"
            if await self._reserve_mail_quota():
                background_tasks.add_task(
                    self._mail.send_confirmation_code_through_email, email, code
                )
            elif settings.demo.fallback_on_quota:
                # The demo must survive a competitor burning the mail quota.
                code = settings.demo.code
                demo_code = code
            else:
                raise EmailQuotaExceededError()

        user_dict["code"] = code
        await self._redis.set(
            name=f"verify_email:{email}",
            value=json.dumps(user_dict),
            ex=300,
        )
        return demo_code

    async def register_user_without_verification(
        self, user_data: UserSchemaAdd
    ) -> User:
        """Create the account right away: no code, no email, no Redis state.

        Used when settings.auth.email_verification is False. We do not check
        that the mailbox exists or belongs to the person; login later compares
        the email and password against what was entered here.
        """
        user_dict = user_data.model_dump(
            exclude={"password_confirm", "turnstile_token"}
        )
        user_dict["email"] = str(user_dict["email"]).strip().lower()

        if await self._crud.get_by_email(user_dict["email"]):
            raise IntegrityConstraintError()

        user_dict["password"] = security.hash_password(user_dict["password"])
        return await self._crud.create(user_dict)

    async def _reserve_mail_quota(self) -> bool:
        """Atomically reserve one email from the daily budget."""
        day = datetime.now(tz=timezone.utc).date().isoformat()
        key = f"mail:quota:{day}"
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, 60 * 60 * 48)
        return count <= settings.mail.daily_limit

    async def verify_email(self, verify_data: VerifyEmailSchema):
        email = str(verify_data.email).strip().lower()
        attempts_key = f"verify_email:attempts:{email}"
        attempts = await self._redis.incr(attempts_key)
        if attempts == 1:
            await self._redis.expire(attempts_key, 300)
        if attempts > 5:
            await self._redis.delete(f"verify_email:{email}")
            raise TooManyRequestsError(
                "Too many incorrect attempts. Request a new confirmation code."
            )

        json_data = await self._redis.get(f"verify_email:{email}")
        if not json_data:
            raise InvalidCodeError()
        redis_data = json.loads(json_data)
        if not secrets.compare_digest(str(verify_data.code), str(redis_data["code"])):
            raise InvalidCodeError()
        redis_data.pop("code")
        await self._redis.delete(f"verify_email:{email}")
        await self._redis.delete(attempts_key)
        return await self._crud.create(redis_data)

    async def login_user(self, user_data: LoginSchema) -> User:
        obj = await self._crud.get_by_email(user_data.email)  # user_data.email
        # returns type EmailStr due to orm that run through model User even when it is select
        if obj is None:
            raise InvalidCredentialsError()
        if obj.is_blocked:
            raise UserBlockedError()
        if not security.verify_password(
            obj.password, user_data.password.get_secret_value()
        ):
            raise InvalidCredentialsError()
        return obj

    async def refresh(self, refresh_token: str) -> User:
        refresh_payload = security.jwt_checker.check_refresh_token(refresh_token)
        user_id = refresh_payload["sub"]
        user = await self._crud.get(user_id)
        if user is None:
            raise TokenValidationError()
        if user.is_blocked:
            raise UserBlockedError()
        the_rest_of_old_token_ttl = refresh_payload["exp"] - int(time.time())
        if the_rest_of_old_token_ttl <= 0:
            raise TokenValidationError()
        token_id = hashlib.sha256(refresh_token.encode()).hexdigest()
        if not await self._redis.set(
            name=f"blacklist:{token_id}",
            value=1,
            nx=True,
            ex=the_rest_of_old_token_ttl,
        ):
            raise TokenValidationError()
        return user

    def _get_current_user_id(self, access_token: str) -> uuid.UUID:
        user_data = security.jwt_checker.check_access_token(access_token)
        try:
            return uuid.UUID(user_data["sub"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TokenValidationError() from exc

    async def get_current_user(self, access_token: str) -> User:
        user_id = self._get_current_user_id(access_token)
        user = await self._crud.get(user_id)
        if user is None or user.is_blocked:
            raise TokenValidationError()
        return user
