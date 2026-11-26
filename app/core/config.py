from functools import cached_property
from pathlib import Path

from pydantic import BaseModel, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

# get this path F:\python\user_service | resolve needs to get the absolute path 100 percent of the time
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class ApiPrefix(BaseModel):
    user: str = "/user"
    auth: str = "/auth"
    v1_prefix: str = "/v1"
    healthcheck: str = "/healthcheck"


class ApiConf(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8005


class LogConf(BaseModel):
    format: str = (
        "[%(asctime)s.%(msecs)03d] %(module)10s:%(lineno)-3d %(levelname)-7s - %(message)s"
    )


class DatabaseConf(BaseModel):
    url: PostgresDsn
    echo: bool = False
    # echo: bool = True


class JWTConf(BaseModel):
    private_key_path: Path
    public_key_path: Path
    access_exp: int = 15
    refresh_exp: int = 30
    algorithm: str = "RS256"

    @cached_property
    def private_key(self) -> str:
        return (BASE_DIR / self.private_key_path).read_text()

    @cached_property
    def public_key(self) -> str:
        return (BASE_DIR / self.public_key_path).read_text()


class RateLimiterConf(BaseModel):
    login: str = "5/15minutes"
    # Keep this high enough for a venue with one shared NAT IP, while the
    # per-email cooldown and the daily mail cap stop quota exhaustion.
    register_limit: str = "10/hour"
    verify_limit: str = "30/15minutes"


class MailConf(BaseModel):
    # smtp | mailtrap_api
    provider: str = "smtp"
    host: str = "sandbox.smtp.mailtrap.io"
    port: int = 2525
    start_tls: bool = True
    from_email: str = "noreply@torty-shop.com"
    username: str = ""
    password: str = ""
    api_url: str = "https://send.api.mailtrap.io/api/send"
    api_token: str = ""
    daily_limit: int = 120


class Redis(BaseModel):
    url: RedisDsn


class CookieConf(BaseModel):
    secure: bool = False
    samesite: str = "lax"
    domain: str | None = None


class DemoConf(BaseModel):
    enabled: bool = False
    code: str = "000000"
    fallback_on_quota: bool = True


class AuthConf(BaseModel):
    # EMAIL VERIFICATION SWITCH.
    #
    # False (current default, no SMTP server available): registration creates
    # the account immediately, no code is generated and no email is sent. Any
    # syntactically valid email is accepted; login still checks the
    # email + password pair that was entered at registration.
    #
    # True: the full flow is used. /auth/register sends a 6-digit code
    # (via MailService / SMTP or Mailtrap, see MailConf) and the account is
    # created only after /auth/verify-email accepts that code.
    #
    # To turn the code flow back on, set CONFIG__AUTH__EMAIL_VERIFICATION=true
    # in .env (or change the default below). No code was deleted.
    email_verification: bool = False


class CorsConf(BaseModel):
    origins: str = ""

    @property
    def origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.origins.split(",") if origin.strip()]


class TurnstileConf(BaseModel):
    enabled: bool = False
    secret: str = ""
    verify_url: str = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env.template", BASE_DIR / ".env"),
        case_sensitive=False,
        env_nested_delimiter="__",
        frozen=True,
        env_prefix="CONFIG__",
        extra="ignore",
    )

    api_prefix: ApiPrefix = ApiPrefix()
    api_conf: ApiConf = ApiConf()
    logging_conf: LogConf = LogConf()
    db: DatabaseConf
    jwt: JWTConf
    limiter: RateLimiterConf = RateLimiterConf()
    mail: MailConf = MailConf()  # only needed when email_verification=True
    redis: Redis
    cookie: CookieConf = CookieConf()
    demo: DemoConf = DemoConf()
    auth: AuthConf = AuthConf()
    cors: CorsConf = CorsConf()
    turnstile: TurnstileConf = TurnstileConf()


settings = Settings()
