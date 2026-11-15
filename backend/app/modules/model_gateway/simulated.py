from __future__ import annotations

import time

from app.modules.model_gateway.base import ModelRequest, ModelResponse

SIMULATED_PREFIX = "[SIMULATED]"


class SimulatedProvider:
    """Explicit non-model adapter. It never calls a model; output is a labelled echo of the input."""

    name = "simulated"

    async def complete(self, request: ModelRequest) -> ModelResponse:
        start = time.perf_counter()
        excerpt = request.prompt[:500]
        suffix = "..." if len(request.prompt) > 500 else ""
        text = (
            f"{SIMULATED_PREFIX} No language model was called. "
            f"Echo of input ({len(request.prompt)} chars, configured model '{request.model}'): "
            f"{excerpt}{suffix}"
        )
        return ModelResponse(
            text=text,
            input_tokens=None,
            output_tokens=None,
            model=request.model,
            latency_ms=int((time.perf_counter() - start) * 1000),
            provider="simulated",
            simulated=True,
        )
