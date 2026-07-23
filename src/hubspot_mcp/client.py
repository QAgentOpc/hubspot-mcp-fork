"""Thin async HTTP client for the HubSpot REST API.

Wraps :mod:`httpx` with:

* Bearer-token authentication from :class:`~hubspot_mcp.config.Settings`.
* JSON encoding/decoding.
* Automatic retry with backoff on rate limits (HTTP 429) and transient 5xx
  errors, honouring HubSpot's ``Retry-After`` header when present.
* A single :class:`HubSpotError` that carries the status code and the parsed
  error body, so tools can surface useful messages to the model.
"""

from __future__ import annotations

import asyncio
from typing import Any, Mapping

import httpx

from .config import Settings, load_settings

# HubSpot private apps allow ~100 requests / 10s; retry a few times on bursts.
_MAX_RETRIES = 4
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class HubSpotError(RuntimeError):
    """An error returned by the HubSpot API or the transport layer."""

    def __init__(self, message: str, *, status_code: int | None = None, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body

    def as_text(self) -> str:
        parts = [str(self)]
        if self.status_code is not None:
            parts.append(f"(HTTP {self.status_code})")
        return " ".join(parts)


class HubSpotClient:
    """Minimal async client over the HubSpot REST API."""

    def __init__(self, settings: Settings | None = None, *, client: httpx.AsyncClient | None = None):
        self._settings = settings or load_settings()
        self._owns_client = client is None
        # No static Authorization header: the token is resolved per request so
        # that each authenticated user's HubSpot token is used (oauth mode).
        # No default Content-Type either: httpx sets it from the body type per
        # request (application/json for ``json=``, multipart for ``files=``); a
        # static application/json default would mislabel file uploads.
        self._client = client or httpx.AsyncClient(
            base_url=self._settings.api_base_url,
            timeout=self._settings.timeout,
            headers={"User-Agent": "hubspot-mcp/0.1.0"},
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _resolve_token(self) -> str:
        """Pick the HubSpot access token for the current request.

        Prefers the authenticated user's token from the OAuth request context
        (oauth mode); falls back to a configured static token (token mode).
        """

        try:  # Only available inside an authenticated request context.
            from fastmcp.server.dependencies import get_access_token

            access = get_access_token()
        except Exception:
            access = None
        if access is not None and access.token:
            return access.token

        if self._settings.access_token:
            return self._settings.access_token

        raise HubSpotError(
            "No HubSpot access token available: the request is not "
            "authenticated and no static HUBSPOT_ACCESS_TOKEN is configured."
        )

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any | None = None,
        token: str | None = None,
    ) -> Any:
        """Perform a request and return the decoded JSON body (or ``None``).

        Args:
            method: HTTP verb, e.g. ``"GET"`` or ``"POST"``.
            path: API path beginning with ``/`` (e.g. ``/crm/v3/objects/contacts``).
            params: Query-string parameters. List/tuple values are sent as
                repeated keys, which is how HubSpot expects ``properties`` etc.
            json: JSON-serialisable request body.
            token: Explicit bearer token; if omitted it is resolved from the
                request context / configured static token.

        Raises:
            HubSpotError: on a non-success response or transport failure.
        """

        bearer = token or self._resolve_token()
        auth_header = {"Authorization": f"Bearer {bearer}"}
        clean_params = _clean_params(params)
        attempt = 0
        while True:
            attempt += 1
            try:
                response = await self._client.request(
                    method.upper(),
                    path,
                    params=clean_params,
                    json=json,
                    headers=auth_header,
                )
            except httpx.RequestError as exc:  # network/timeout/DNS etc.
                if attempt <= _MAX_RETRIES:
                    await asyncio.sleep(_backoff_seconds(attempt))
                    continue
                raise HubSpotError(f"Request to HubSpot failed: {exc}") from exc

            if response.status_code in _RETRYABLE_STATUS and attempt <= _MAX_RETRIES:
                await asyncio.sleep(_retry_delay(response, attempt))
                continue

            if response.is_success:
                return _decode(response)

            raise _error_from_response(response)

    async def upload(
        self,
        path: str,
        *,
        files: Mapping[str, Any],
        data: Mapping[str, Any] | None = None,
        token: str | None = None,
    ) -> Any:
        """POST a ``multipart/form-data`` body (file upload) and decode the JSON.

        httpx derives the multipart ``Content-Type`` (with boundary) from
        ``files``; the client carries no default Content-Type so this is not
        overridden. File parts are passed as ``(filename, bytes, content_type)``
        so a retry re-encodes from the same bytes rather than a spent stream.

        Args:
            path: API path beginning with ``/`` (e.g. ``/files/v3/files``).
            files: Multipart file parts, e.g.
                ``{"file": ("a.pdf", b"...", "application/pdf")}``.
            data: Additional non-file form fields (string values).
            token: Explicit bearer token; resolved from context if omitted.

        Raises:
            HubSpotError: on a non-success response or transport failure.
        """

        bearer = token or self._resolve_token()
        auth_header = {"Authorization": f"Bearer {bearer}"}
        attempt = 0
        while True:
            attempt += 1
            try:
                response = await self._client.post(
                    path,
                    files=dict(files),
                    data=dict(data or {}),
                    headers=auth_header,
                )
            except httpx.RequestError as exc:  # network/timeout/DNS etc.
                if attempt <= _MAX_RETRIES:
                    await asyncio.sleep(_backoff_seconds(attempt))
                    continue
                raise HubSpotError(f"Request to HubSpot failed: {exc}") from exc

            if response.status_code in _RETRYABLE_STATUS and attempt <= _MAX_RETRIES:
                await asyncio.sleep(_retry_delay(response, attempt))
                continue

            if response.is_success:
                return _decode(response)

            raise _error_from_response(response)


def _clean_params(params: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Drop ``None`` values and normalise booleans for the query string."""

    if not params:
        return None
    cleaned: dict[str, Any] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            cleaned[key] = "true" if value else "false"
        else:
            cleaned[key] = value
    return cleaned or None


def _decode(response: httpx.Response) -> Any:
    if response.status_code == 204 or not response.content:
        return None
    try:
        return response.json()
    except ValueError:
        return response.text


def _error_from_response(response: httpx.Response) -> HubSpotError:
    try:
        body = response.json()
        message = body.get("message") if isinstance(body, dict) else None
    except ValueError:
        body = response.text
        message = None
    return HubSpotError(
        message or f"HubSpot API returned HTTP {response.status_code}",
        status_code=response.status_code,
        body=body,
    )


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            pass
    return _backoff_seconds(attempt)


def _backoff_seconds(attempt: int) -> float:
    # Exponential backoff: 0.5s, 1s, 2s, 4s ...
    return 0.5 * (2 ** (attempt - 1))
