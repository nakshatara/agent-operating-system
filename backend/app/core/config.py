from __future__ import annotations

import json
from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-insecure-secret-do-not-use-in-prod"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    env: str = "development"
    log_level: str = "INFO"

    # PostgreSQL (owner of transactional state)
    database_url: str = "postgresql+asyncpg://agentos:agentos@localhost:5432/agentos"

    # Redis (rate limiting + live-update pub/sub)
    redis_url: str = "redis://localhost:6379/0"

    # Neo4j (owner of relationships; projection of events)
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4j"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_events_topic: str = "agentos.events"
    kafka_dlq_topic: str = "agentos.events.dlq"

    # Auth
    jwt_secret: str = DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60

    cors_origins: str = "http://localhost:3000"

    # Providers
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    openai_extra_models: str = ""
    pricing_json: str | None = None  # {"provider:model": {"input_per_mtok": x, "output_per_mtok": y}}
    provider_timeout_seconds: float = 60.0
    provider_max_retries: int = 3
    provider_backoff_seconds: float = 1.0
    execution_timeout_seconds: float = 120.0

    # Workers / events
    background_workers_enabled: bool = True
    relay_poll_interval_seconds: float = 1.0
    relay_batch_size: int = 50
    consumer_max_retries: int = 3

    rate_limit_auth_per_minute: int = 20

    @field_validator("anthropic_api_key", "openai_api_key", "pricing_json", mode="before")
    @classmethod
    def _blank_to_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @model_validator(mode="after")
    def _check_prod_secret(self) -> Settings:
        if self.env.lower() == "production" and (
            self.jwt_secret == DEV_JWT_SECRET or len(self.jwt_secret) < 32
        ):
            raise ValueError("JWT_SECRET must be set to a random value (>=32 chars) in production")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def openai_extra_model_list(self) -> list[str]:
        return [m.strip() for m in self.openai_extra_models.split(",") if m.strip()]

    def provider_api_key(self, provider: str) -> str | None:
        if provider == "anthropic":
            return self.anthropic_api_key
        if provider == "openai":
            return self.openai_api_key
        return None

    def pricing(self) -> dict[str, dict[str, float]]:
        if not self.pricing_json:
            return {}
        try:
            data = json.loads(self.pricing_json)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
