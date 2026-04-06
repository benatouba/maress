import secrets
import warnings
from typing import Annotated, Any, Literal, Self

from pydantic import (
    AnyUrl,
    BeforeValidator,
    EmailStr,
    PostgresDsn,
    computed_field,
    model_validator,
)
from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from logging import Logger


def parse_cors(v: list[Any] | str) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",") if i.strip()]
    return v


class Settings(BaseSettings):
    model_config = SettingsConfigDict(  # pyright: ignore[reportUnannotatedClassAttribute]
        # Use top level .env file (one level above ./backend/)
        env_file="../.env.local",
        env_ignore_empty=True,
        extra="ignore",
    )
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8 * 60
    FRONTEND_HOST: str = "http://localhost:3000"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"

    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str,
        BeforeValidator(parse_cors),
    ] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS] + [
            self.FRONTEND_HOST,
        ]

    PROJECT_NAME: str
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> MultiHostUrl:  # noqa: N802
        return MultiHostUrl.build(
            scheme="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: EmailStr | None = None
    emails_from_name: str | None = None  # lowercase because it can be altered

    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if not self.emails_from_name:
            self.emails_from_name = self.PROJECT_NAME
        return self

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48

    @computed_field  # type: ignore[prop-decorator]
    @property
    def emails_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.EMAILS_FROM_EMAIL)

    EMAIL_TEST_USER: EmailStr = "test@example.com"
    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_PASSWORD: str

    ZOTERO_API_KEY: str
    ZOTERO_USER_ID: str
    ZOTERO_LIBRARY_TYPE: Literal["user", "group"] = "user"

    ENCRYPTION_KEY: str

    # NLP Configuration
    # SPACY_MODEL: str = "en_core_web_lg"  # Set up in nlp.model_config.py

    # Geocoding Configuration
    GEOCODING_CACHE_TTL: int = 60 * 60 * 24 * 30  # 30 days in seconds
    GEOCODING_RATE_LIMIT: float = 1.0  # requests per second for Nominatim
    GEOCODING_ALLOW_LIVE_REQUESTS: bool = True
    GEOCODING_MAX_CANDIDATES_PER_DOC: int = 20
    GEOCODING_MIN_CANDIDATE_CONFIDENCE: float = 0.55
    GEOCODING_STRICT_OTHER_SECTION_MIN_CONFIDENCE: float = 0.8
    GEOCODING_REJECT_DETERMINER_PREFIX: bool = True
    GEOCODING_REJECT_NON_LOCATION_CONTENT: bool = True
    GEOCODING_REQUIRE_CAPITALIZED_MULTI_TOKEN: bool = True
    GEOCODING_MAX_DISTANCE_WITHOUT_BIAS_KM: float = 3000.0
    GEOCODING_MAX_DISTANCE_WITH_BIAS_KM: float = 1200.0
    GEOCODING_MAX_DISTANCE_PER_CANDIDATE_KM: float = 1800.0

    # Map location-search API configuration
    GEOCODING_SEARCH_PROVIDER: Literal["nominatim", "mapbox"] = "nominatim"
    GEOCODING_SEARCH_NOMINATIM_URL: str = "https://nominatim.openstreetmap.org/search"
    GEOCODING_SEARCH_MAPBOX_ACCESS_TOKEN: str | None = None
    GEOCODING_SEARCH_DEFAULT_LIMIT: int = 8
    GEOCODING_SEARCH_MAX_LIMIT: int = 20
    GEOCODING_SEARCH_RATE_LIMIT: float = 1.0
    GEOCODING_SEARCH_CACHE_TTL: int = 60 * 10
    GEOCODING_SEARCH_COUNTRYCODES: str | None = None

    # GeoNames Configuration (for entity linking/disambiguation)
    # Register free account at: https://www.geonames.org/login
    GEONAMES_USERNAME: str | None = None

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.ENVIRONMENT == "local":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        self._check_default_secret("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD)
        self._check_default_secret("CELERY_BROKER_URL", self.CELERY_BROKER_URL)
        self._check_default_secret("CELERY_RESULT_BACKEND", self.CELERY_RESULT_BACKEND)
        self._check_default_secret("FIRST_SUPERUSER_PASSWORD", self.FIRST_SUPERUSER_PASSWORD)
        self._check_default_secret("ZOTERO_API_KEY", self.ZOTERO_API_KEY)
        self._check_default_secret("ZOTERO_USER_ID", self.ZOTERO_USER_ID)
        self._check_default_secret("ZOTERO_LIBRARY_TYPE", self.ZOTERO_LIBRARY_TYPE)
        self._check_default_secret("ENCRYPTION_KEY", self.ENCRYPTION_KEY)

        return self


settings = Settings()  # pyright: ignore[reportCallIssue]


class ConfigError(Exception):
    """Custom exception for configuration errors."""
