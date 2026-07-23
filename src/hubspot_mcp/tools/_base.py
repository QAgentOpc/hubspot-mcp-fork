"""Shared helpers for tool modules."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from ..client import HubSpotClient, HubSpotError

try:  # ToolError gives the client a clean error message without a traceback.
    from fastmcp.exceptions import ToolError
except Exception:  # pragma: no cover - fallback if the import path changes.
    ToolError = RuntimeError  # type: ignore[assignment, misc]

# A zero-arg callable that returns the shared HubSpot client.
ClientGetter = Callable[[], HubSpotClient]


async def api(
    get_client: ClientGetter,
    method: str,
    path: str,
    *,
    params: Mapping[str, Any] | None = None,
    json: Any | None = None,
) -> Any:
    """Call the HubSpot API, converting transport errors into ``ToolError``."""

    try:
        return await get_client().request(method, path, params=params, json=json)
    except HubSpotError as exc:
        raise ToolError(exc.as_text()) from exc


async def upload(
    get_client: ClientGetter,
    path: str,
    *,
    files: Mapping[str, Any],
    data: Mapping[str, Any] | None = None,
) -> Any:
    """Upload a multipart body, converting transport errors into ``ToolError``."""

    try:
        return await get_client().upload(path, files=files, data=data)
    except HubSpotError as exc:
        raise ToolError(exc.as_text()) from exc
