"""Runtime configuration for the HubSpot MCP server.

Two authentication modes are supported:

* ``oauth`` (recommended for hosted, multi-user deployments) — the server runs
  over HTTP and acts as an OAuth proxy in front of HubSpot. Each user logs in
  through their browser (driven by the MCP client) and the server uses that
  user's HubSpot access token per request. Requires a HubSpot **public app**
  (client id + secret) and a publicly reachable ``HUBSPOT_SERVER_URL``.

* ``token`` (simple local/dev) — the server runs over stdio and uses a single
  static HubSpot **private app** access token for all requests.

Configuration is read from environment variables (a local ``.env`` file is
loaded automatically when present).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

DEFAULT_API_BASE_URL = "https://api.hubapi.com"
DEFAULT_TIMEOUT = 30.0

# HubSpot OAuth 2.0 endpoints.
HUBSPOT_AUTHORIZE_URL = "https://app.hubspot.com/oauth/authorize"
HUBSPOT_TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"
# Opaque-token metadata endpoint used to validate access tokens.
HUBSPOT_TOKEN_INFO_URL = "https://api.hubapi.com/oauth/v1/access-tokens"

# A sensible default scope set for CRM + marketing automation. Override with
# HUBSPOT_SCOPES. These must also be enabled on the HubSpot app itself.
DEFAULT_SCOPES = [
    # ── CRM object records (generic object/engagement/association tools) ────────
    "crm.objects.contacts.read",  # contacts + notes/tasks engagements
    "crm.objects.contacts.write",
    "crm.objects.companies.read",
    "crm.objects.companies.write",
    "crm.objects.deals.read",
    "crm.objects.deals.write",
    "crm.objects.products.read",  # products / line items
    "crm.objects.products.write",
    "files",  # file manager tools (combined read+write scope)
    # NB: custom objects (crm.objects.custom.*) require an Enterprise plan and are
    # intentionally omitted — requesting them on a non-Enterprise portal can make
    # HubSpot reject the whole authorization. The object-schema tools and custom
    # object_type values will 403 at call time without them.
    "tickets",  # ticket records (single combined read/write scope)
    "crm.objects.owners.read",  # owners tools
    "crm.schemas.contacts.read",  # property / schema reads
    # ── Lists ──────────────────────────────────────────────────────────────────
    "crm.lists.read",
    "crm.lists.write",
    # ── Marketing: campaigns (needs Marketing Hub Pro+) ─────────────────────────
    "marketing.campaigns.read",
    "marketing.campaigns.write",
    "marketing.campaigns.revenue.read",  # campaign revenue report tool
    # ── Marketing: emails & forms (Marketing/Content Hub) ───────────────────────
    "content",  # marketing emails CRUD + statistics
    # NB: marketing-email and transactional-email are intentionally omitted — they
    # require Marketing Hub levels / the paid Transactional Email add-on that not
    # every portal has, and requesting an ungranted scope fails authorization. With
    # them omitted, email publish/unpublish and the single-send tools will 403 at
    # call time, but everything else still authorizes. Add them via HUBSPOT_SCOPES
    # on a portal that has the corresponding subscription.
    "forms",  # forms tools
    # ── Marketing: events ───────────────────────────────────────────────────────
    "crm.objects.marketing_events.read",
    "crm.objects.marketing_events.write",
    # ── Subscriptions / communication preferences ───────────────────────────────
    "communication_preferences.read",
    "communication_preferences.read_write",
    # ── Automation: workflows / flows ───────────────────────────────────────────
    "automation",
    # ── Automation: sequences (Sales/Service Pro). Not yet called by any tool, but
    #    the registered HubSpot app marks them required, so they must be requested
    #    for authorization to succeed. ───────────────────────────────────────────
    "automation.sequences.read",
    "automation.sequences.enrollments.write",
]


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    """Resolved server settings."""

    auth_mode: str  # "oauth" | "token"
    api_base_url: str = DEFAULT_API_BASE_URL
    timeout: float = DEFAULT_TIMEOUT

    # token mode
    access_token: str | None = None

    # oauth mode
    client_id: str | None = None
    client_secret: str | None = None
    server_url: str | None = None
    scopes: list[str] = field(default_factory=lambda: list(DEFAULT_SCOPES))
    host: str = "0.0.0.0"
    port: int = 8000
    forward_pkce: bool = False
    require_consent: bool = True

    # deployment
    transport: str = "stdio"  # "stdio" | "http"
    disabled_tools: tuple[str, ...] = ()


def _split_scopes(raw: str) -> list[str]:
    return [s for s in raw.replace(",", " ").split() if s]


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from exc


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def load_settings() -> Settings:
    """Build :class:`Settings` from the environment.

    The mode is taken from ``HUBSPOT_AUTH_MODE`` if set, otherwise inferred:
    ``oauth`` when a client id is present, else ``token``.

    Raises:
        ConfigError: if required values for the resolved mode are missing.
    """

    api_base_url = (
        os.environ.get("HUBSPOT_BASE_URL", DEFAULT_API_BASE_URL).strip().rstrip("/")
        or DEFAULT_API_BASE_URL
    )
    timeout = _float_env("HUBSPOT_TIMEOUT", DEFAULT_TIMEOUT)

    client_id = os.environ.get("HUBSPOT_CLIENT_ID", "").strip() or None
    client_secret = os.environ.get("HUBSPOT_CLIENT_SECRET", "").strip() or None
    access_token = os.environ.get("HUBSPOT_ACCESS_TOKEN", "").strip() or None

    mode = os.environ.get("HUBSPOT_AUTH_MODE", "").strip().lower()
    if not mode:
        mode = "oauth" if client_id else "token"
    if mode not in ("oauth", "token"):
        raise ConfigError(
            f"HUBSPOT_AUTH_MODE must be 'oauth' or 'token', got {mode!r}"
        )

    transport = os.environ.get("HUBSPOT_TRANSPORT", "stdio").strip() or "stdio"
    if transport not in ("stdio", "http"):
        raise ConfigError(
            f"HUBSPOT_TRANSPORT must be 'stdio' or 'http', got {transport!r}"
        )

    disabled_raw = os.environ.get("HUBSPOT_DISABLED_TOOLS", "").strip()
    disabled_tools = tuple(_split_scopes(disabled_raw)) if disabled_raw else ()

    if mode == "token":
        if not access_token:
            raise ConfigError(
                "token mode requires HUBSPOT_ACCESS_TOKEN (a HubSpot private app "
                "token). For browser-based login set HUBSPOT_AUTH_MODE=oauth and "
                "provide HUBSPOT_CLIENT_ID / HUBSPOT_CLIENT_SECRET / HUBSPOT_SERVER_URL."
            )
        return Settings(
            auth_mode="token",
            api_base_url=api_base_url,
            timeout=timeout,
            access_token=access_token,
            host=os.environ.get("HUBSPOT_HOST", "0.0.0.0").strip() or "0.0.0.0",
            port=_int_env("HUBSPOT_PORT", 8000),
            transport=transport,
            disabled_tools=disabled_tools,
        )

    # oauth mode
    server_url = os.environ.get("HUBSPOT_SERVER_URL", "").strip().rstrip("/") or None
    missing = [
        name
        for name, val in (
            ("HUBSPOT_CLIENT_ID", client_id),
            ("HUBSPOT_CLIENT_SECRET", client_secret),
            ("HUBSPOT_SERVER_URL", server_url),
        )
        if not val
    ]
    if missing:
        raise ConfigError(
            "oauth mode requires " + ", ".join(missing) + ". Create a HubSpot "
            "public app (Settings > Integrations > Private Apps is NOT enough — "
            "use the developer account app with OAuth), set its client id/secret, "
            "and set HUBSPOT_SERVER_URL to this server's public https URL."
        )

    scopes_raw = os.environ.get("HUBSPOT_SCOPES", "").strip()
    scopes = _split_scopes(scopes_raw) if scopes_raw else list(DEFAULT_SCOPES)

    return Settings(
        auth_mode="oauth",
        api_base_url=api_base_url,
        timeout=timeout,
        access_token=access_token,  # optional fallback, usually None in oauth mode
        client_id=client_id,
        client_secret=client_secret,
        server_url=server_url,
        scopes=scopes,
        host=os.environ.get("HUBSPOT_HOST", "0.0.0.0").strip() or "0.0.0.0",
        port=_int_env("HUBSPOT_PORT", 8000),
        forward_pkce=_bool_env("HUBSPOT_FORWARD_PKCE", False),
        require_consent=_bool_env("HUBSPOT_REQUIRE_CONSENT", True),
        transport=transport,
        disabled_tools=disabled_tools,
    )
