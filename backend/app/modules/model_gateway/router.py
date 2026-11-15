from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.deps import Principal, get_current_principal
from app.modules.model_gateway import registry

router = APIRouter(prefix="/models", tags=["models"])


class ModelOut(BaseModel):
    provider: str
    id: str
    live_available: bool
    input_per_mtok: float | None
    output_per_mtok: float | None


class ModelListOut(BaseModel):
    default_provider: str
    default_model: str
    models: list[ModelOut]


@router.get("", response_model=ModelListOut)
async def list_models(_: Principal = Depends(get_current_principal)) -> ModelListOut:
    return ModelListOut(
        default_provider=registry.DEFAULT_PROVIDER,
        default_model=registry.DEFAULT_MODEL,
        models=[
            ModelOut(
                provider=m.provider,
                id=m.id,
                live_available=registry.provider_configured(m.provider),
                input_per_mtok=m.input_per_mtok,
                output_per_mtok=m.output_per_mtok,
            )
            for m in registry.list_models()
        ],
    )
