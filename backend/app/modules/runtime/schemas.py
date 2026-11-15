from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ExecutionCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)


class ExecutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    agent_id: uuid.UUID
    requested_by: uuid.UUID | None
    input_prompt: str
    output: str | None
    error: str | None
    status: str
    mode: str
    provider: str
    model: str
    agent_version: int
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int | None
    cost_usd: float | None
    trace_id: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class ExecutionPage(BaseModel):
    items: list[ExecutionOut]
    total: int
    limit: int
    offset: int
