from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiPrefix(BaseModel):
    user: str = "/user"
    auth: str = "/auth"
    v1_prefix: str = "/v1"


class ApiConf(BaseModel):
    # TODO you should remember about docker requests
    host: str = "0.0.0.0"
    port: int = 8001


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.template", ".env"),
        case_sensitive=False,
        env_nested_delimiter="__",
        frozen=True,
        extra="forbid",
    )

    api_prefix: ApiPrefix = ApiPrefix()
    api_conf: ApiConf = ApiConf()


settings = Settings()
