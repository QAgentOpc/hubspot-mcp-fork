"""Tests for the Files API tools (upload + attach-to-deal) and note attachments.

Uses respx to mock ``api.hubapi.com`` and the in-memory FastMCP client to drive
the tools, so we assert the exact multipart upload and the upload→note→associate
chain without touching real HubSpot.
"""

import base64
import json

import httpx
import pytest
import respx
from fastmcp import Client

BASE = "https://api.hubapi.com"

_B64 = base64.b64encode(b"hello bytes").decode()


@pytest.fixture
def server():
    import hubspot_mcp.server as srv

    srv._client = None  # fresh client per test
    return srv


@respx.mock
async def test_upload_file_sends_multipart(server):
    route = respx.post(f"{BASE}/files/v3/files").mock(
        return_value=httpx.Response(201, json={"id": "42", "url": "https://f/42"})
    )
    async with Client(server.mcp) as client:
        await client.call_tool(
            "hubspot_upload_file",
            {"filename": "report.pdf", "data_base64": _B64, "folder_path": "/deals"},
        )

    assert route.called
    req = route.calls.last.request
    # httpx set a multipart content-type (not the old json default).
    assert req.headers["content-type"].startswith("multipart/form-data; boundary=")
    body = req.content
    assert b'filename="report.pdf"' in body
    assert b"hello bytes" in body  # the decoded file bytes rode the multipart body
    assert b"PRIVATE" in body  # options.access default
    assert b'name="folderPath"' in body and b"/deals" in body
    assert req.headers["Authorization"] == "Bearer tok"


@respx.mock
async def test_upload_file_rejects_bad_base64(server):
    route = respx.post(f"{BASE}/files/v3/files").mock(return_value=httpx.Response(201))
    async with Client(server.mcp) as client:
        with pytest.raises(Exception) as exc:
            await client.call_tool(
                "hubspot_upload_file",
                {"filename": "a.txt", "data_base64": "not valid base64!!"},
            )
    assert "base64" in str(exc.value)
    assert not route.called  # rejected before any HTTP call


@respx.mock
async def test_upload_file_rejects_bad_access(server):
    route = respx.post(f"{BASE}/files/v3/files").mock(return_value=httpx.Response(201))
    async with Client(server.mcp) as client:
        with pytest.raises(Exception) as exc:
            await client.call_tool(
                "hubspot_upload_file",
                {"filename": "a.txt", "data_base64": _B64, "access": "WORLD"},
            )
    assert "access" in str(exc.value)
    assert not route.called


@respx.mock
async def test_attach_file_to_deal_chains_upload_note_associate(server):
    up = respx.post(f"{BASE}/files/v3/files").mock(
        return_value=httpx.Response(201, json={"id": "99", "url": "https://f/99"})
    )
    note = respx.post(f"{BASE}/crm/v3/objects/notes").mock(
        return_value=httpx.Response(201, json={"id": "77"})
    )
    assoc = respx.put(
        f"{BASE}/crm/v4/objects/notes/77/associations/default/deals/5"
    ).mock(return_value=httpx.Response(200, json={}))

    async with Client(server.mcp) as client:
        await client.call_tool(
            "hubspot_attach_file_to_deal",
            {
                "deal_id": "5",
                "filename": "contract.pdf",
                "data_base64": _B64,
                "note_body": "signed",
            },
        )

    assert up.called and note.called and assoc.called
    note_body = json.loads(note.calls.last.request.content)
    props = note_body["properties"]
    assert props["hs_note_body"] == "signed"
    # The note carries the just-uploaded file's id as its attachment.
    assert props["hs_attachment_ids"] == "99"


@respx.mock
async def test_create_note_sets_attachment_ids(server):
    note = respx.post(f"{BASE}/crm/v3/objects/notes").mock(
        return_value=httpx.Response(201, json={"id": "1"})
    )
    async with Client(server.mcp) as client:
        await client.call_tool(
            "hubspot_create_note",
            {"body": "see files", "attachment_ids": ["10", "20"]},
        )

    props = json.loads(note.calls.last.request.content)["properties"]
    assert props["hs_attachment_ids"] == "10;20"
