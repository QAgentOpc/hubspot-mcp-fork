"""FastMCP server definition for HubSpot.

Creates the :class:`FastMCP` instance (with OAuth in oauth mode), manages a
lazily-created shared :class:`~hubspot_mcp.client.HubSpotClient`, and registers
all tool modules.
"""

from __future__ import annotations

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import __version__
from .auth import build_auth
from .client import HubSpotClient
from .config import Settings, load_settings
from .tools import register_all

settings: Settings = load_settings()
auth = build_auth(settings)

mcp = FastMCP(
    name="hubspot",
    auth=auth,
    instructions=(
        "Tools for the HubSpot CRM and Marketing APIs (campaigns, marketing "
        "emails, forms, lists, subscriptions, marketing events, automation "
        "flows). Most CRM data is accessed through the generic object tools "
        "(hubspot_list_objects, hubspot_get_object, hubspot_create_object, "
        "hubspot_update_object, hubspot_delete_object, hubspot_search_objects) "
        "by passing an object_type such as 'contacts', 'companies', 'deals', or "
        "'tickets'. Use hubspot_list_properties to discover available fields "
        "before reading/writing them."
    ),
)

# A single client is shared across all tool calls; it is created on first use.
# The per-request HubSpot token is resolved inside the client, so the same
# instance safely serves every authenticated user.
_client: HubSpotClient | None = None


def get_client() -> HubSpotClient:
    global _client
    if _client is None:
        _client = HubSpotClient(settings)
    return _client


register_all(mcp, get_client, disabled_tools=settings.disabled_tools)


# Unauthenticated health endpoints for Kubernetes probes (HTTP/oauth mode).
# These are plain HTTP routes outside the MCP protocol and require no token.
@mcp.custom_route("/healthz", methods=["GET"], include_in_schema=False)
async def healthz(_request: Request) -> JSONResponse:
    """Liveness: the process is up and serving HTTP."""
    return JSONResponse({"status": "ok", "service": "hubspot-mcp", "version": __version__})


@mcp.custom_route("/readyz", methods=["GET"], include_in_schema=False)
async def readyz(_request: Request) -> JSONResponse:
    """Readiness: configuration loaded and ready to accept requests.

    Kept dependency-free (no outbound HubSpot call) so the probe can't be made
    to fail by HubSpot latency or per-user token state.
    """
    return JSONResponse({"status": "ready", "auth_mode": settings.auth_mode})
