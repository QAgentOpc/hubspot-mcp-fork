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


class _FilteredMCP:
    """Wraps a FastMCP instance, skipping registration of denied tools."""

    def __init__(self, mcp, disabled: frozenset[str]) -> None:
        self._mcp = mcp
        self._disabled = disabled

    def tool(self, *args, **kwargs):
        real = self._mcp.tool(*args, **kwargs)

        def decorator(fn):
            if fn.__name__ in self._disabled:
                return fn  # not registered
            return real(fn)

        return decorator

    def __getattr__(self, name):
        return getattr(self._mcp, name)


def register_all(mcp, get_client, disabled_tools: tuple[str, ...] = ()) -> None:
    if disabled_tools:
        mcp = _FilteredMCP(mcp, frozenset(disabled_tools))
    for module in REGISTRARS:
        module.register(mcp, get_client)
