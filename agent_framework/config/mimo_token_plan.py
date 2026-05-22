from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from .settings import LlmSettings


@dataclass(frozen=True)
class MimoPreflightResult:
    model: str
    base_url: str
    available_models: tuple[str, ...]


def preflight_mimo_token_plan(settings: LlmSettings) -> MimoPreflightResult:
    if not settings.api_key:
        raise RuntimeError("missing MiMo Token Plan API key")

    models_url = f"{settings.base_url.rstrip('/')}/models"
    request = urllib.request.Request(
        models_url,
        headers={
            "Authorization": f"Bearer {settings.api_key}",
            "api-key": settings.api_key,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"MiMo Token Plan auth preflight failed: HTTP {exc.code}: {error_body}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"MiMo Token Plan auth preflight failed: {exc}") from exc

    payload = json.loads(body)
    available_models = tuple(
        str(item["id"])
        for item in payload.get("data", [])
        if isinstance(item, dict) and "id" in item
    )
    if settings.model not in available_models:
        raise RuntimeError(
            "MiMo Token Plan model is not available: "
            f"{settings.model}. Available models: {', '.join(available_models)}"
        )

    return MimoPreflightResult(
        model=settings.model,
        base_url=settings.base_url,
        available_models=available_models,
    )
