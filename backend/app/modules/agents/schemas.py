from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.modules.agents.lifecycle import available_actions
from app.modules.agents.readiness import compute_readiness
from app.modules.model_gateway.registry import DEFAULT_MODEL, DEFAULT_PROVIDER

ExecutionMode = Literal["simulated", "live"]


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    system_instructions: str = Field(default="", max_length=20000)
    objectives: list[str] = Field(default_factory=list, max_length=20)
    provider: str = DEFAULT_PROVIDER
    model: str = DEFAULT_MODEL
    autonomy_level: int = Field(default=1, ge=1, le=4)
    supervisor_agent_id: uuid.UUID | None = None
    execution_mode: ExecutionMode = "simulated"


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    role: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    system_instructions: str | None = Field(default=None, max_length=20000)
    objectives: list[str] | None = Field(default=None, max_length=20)
    provider: str | None = None
    model: str | None = None
    autonomy_level: int | None = Field(default=None, ge=1, le=4)
    supervisor_agent_id: uuid.UUID | None = None
    execution_mode: ExecutionMode | None = None


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    role: str
    description: str
    system_instructions: str
    objectives: list[str]
    provider: str
    model: str
    autonomy_level: int
    supervisor_agent_id: uuid.UUID | None
    execution_mode: str
    status: str
    version: int
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def readiness(self) -> str:
        return compute_readiness(self.execution_mode, self.provider)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def available_actions(self) -> list[str]:
        return available_actions(self.status)


class AgentPage(BaseModel):
    items: list[AgentOut]
    total: int
    limit: int
    offset: int
