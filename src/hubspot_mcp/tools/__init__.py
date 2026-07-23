"""Tool modules for the HubSpot MCP server.

Each module exposes a ``register(mcp, get_client)`` function that attaches its
tools to the shared :class:`FastMCP` instance.
"""

from . import (
    associations,
    automation,
    campaigns,
    email_send,
    engagements,
    files,
    forms,
    lists,
    marketing_emails,
    marketing_events,
    misc,
    objects,
    owners,
    pipelines,
    properties,
    subscriptions,
)

REGISTRARS = (
    # CRM
    objects,
    properties,
    associations,
    owners,
    pipelines,
    engagements,
    files,
    lists,
    # Marketing
    campaigns,
    marketing_emails,
    email_send,
    forms,
    marketing_events,
    subscriptions,
    automation,
    # Account / schemas
    misc,
)


def register_all(mcp, get_client) -> None:
    for module in REGISTRARS:
        module.register(mcp, get_client)
