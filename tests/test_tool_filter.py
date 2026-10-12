"""Tests for the HUBSPOT_DISABLED_TOOLS tool denylist.

The server module loads settings at import time, so each test sets the env vars
then reloads ``hubspot_mcp.server`` (re-registering tools on a fresh FastMCP
instance) and restores the unfiltered module afterwards.
"""

import asyncio
import importlib

import pytest


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("HUBSPOT_AUTH_MODE", "token")
    import hubspot_mcp.server as srv

    saved = dict(srv.__dict__)  # full module state (mcp, settings, auth, _client, ...)
    importlib.reload(srv)
    yield srv
    srv.__dict__.clear()
    srv.__dict__.update(saved)  # restore pre-test module state for later tests


def _tool_names(srv):
    return {t.name for t in asyncio.run(srv.mcp.list_tools())}


def test_disabled_tools_are_not_registered(server, monkeypatch):
    monkeypatch.setenv(
        "HUBSPOT_DISABLED_TOOLS",
        "hubspot_delete_object hubspot_send_transactional_email",
    )
    importlib.reload(server)
    names = _tool_names(server)
    assert "hubspot_delete_object" not in names
    assert "hubspot_send_transactional_email" not in names
    assert "hubspot_get_object" in names
    assert "hubspot_list_objects" in names


def test_tools_registered_when_disabled_tools_unset(server, monkeypatch):
    monkeypatch.delenv("HUBSPOT_DISABLED_TOOLS", raising=False)
    importlib.reload(server)
    assert "hubspot_delete_object" in _tool_names(server)
