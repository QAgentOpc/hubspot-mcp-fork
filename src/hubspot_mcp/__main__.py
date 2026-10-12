"""Console entry point for the HubSpot MCP server.

* ``oauth`` mode runs over HTTP (Streamable HTTP) so MCP clients can perform the
  browser-based OAuth handshake and connect remotely.
* ``token`` mode runs over stdio, which is what local MCP clients expect when
  launching the server as a subprocess; it can also serve HTTP by setting
  ``HUBSPOT_TRANSPORT=http`` (e.g. inside a private docker network).
"""

from __future__ import annotations

import sys

from .config import ConfigError


def main() -> None:
    # Import (and thus configuration loading) happens here so misconfiguration
    # fails fast with a clear message rather than on the first tool call.
    try:
        from .server import mcp, settings
    except ConfigError as exc:
        print(f"hubspot-mcp: configuration error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    use_http = settings.auth_mode == "oauth" or settings.transport == "http"
    if use_http:
        note = (
            "OAuth proxy in front of HubSpot."
            if settings.auth_mode == "oauth"
            else "token mode; relying on network isolation for access control."
        )
        print(
            f"hubspot-mcp: serving over HTTP on {settings.host}:{settings.port} ({note})",
            file=sys.stderr,
        )
        mcp.run(transport="http", host=settings.host, port=settings.port)
    else:
        mcp.run()  # stdio


if __name__ == "__main__":
    main()
