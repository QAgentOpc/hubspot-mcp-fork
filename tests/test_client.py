import httpx
import pytest
import respx

from hubspot_mcp.client import HubSpotClient, HubSpotError, _clean_params
from hubspot_mcp.config import Settings

BASE = "https://api.hubapi.com"


def make_client() -> HubSpotClient:
    return HubSpotClient(
        Settings(auth_mode="token", access_token="tok", api_base_url=BASE, timeout=5.0)
    )


def test_clean_params_drops_none_and_normalises_bools():
    assert _clean_params({"a": None, "b": True, "c": False, "d": 1}) == {
        "b": "true",
        "c": "false",
        "d": 1,
    }
    assert _clean_params(None) is None
    assert _clean_params({"a": None}) is None


@respx.mock
async def test_request_sends_bearer_and_decodes_json():
    route = respx.get(f"{BASE}/crm/v3/objects/contacts").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    client = make_client()
    try:
        result = await client.request("GET", "/crm/v3/objects/contacts")
    finally:
        await client.aclose()

    assert result == {"results": []}
    assert route.calls.last.request.headers["Authorization"] == "Bearer tok"


@respx.mock
async def test_request_repeats_list_params():
    route = respx.get(f"{BASE}/crm/v3/objects/contacts").mock(
        return_value=httpx.Response(200, json={})
    )
    client = make_client()
    try:
        await client.request(
            "GET", "/crm/v3/objects/contacts", params={"properties": ["email", "firstname"]}
        )
    finally:
        await client.aclose()

    url = str(route.calls.last.request.url)
    assert "properties=email" in url and "properties=firstname" in url


@respx.mock
async def test_request_204_returns_none():
    respx.delete(f"{BASE}/crm/v3/objects/contacts/1").mock(
        return_value=httpx.Response(204)
    )
    client = make_client()
    try:
        assert await client.request("DELETE", "/crm/v3/objects/contacts/1") is None
    finally:
        await client.aclose()


@respx.mock
async def test_error_raised_with_status_and_body():
    respx.get(f"{BASE}/crm/v3/objects/contacts/missing").mock(
        return_value=httpx.Response(404, json={"message": "resource not found"})
    )
    client = make_client()
    try:
        with pytest.raises(HubSpotError) as exc:
            await client.request("GET", "/crm/v3/objects/contacts/missing")
    finally:
        await client.aclose()

    assert exc.value.status_code == 404
    assert "resource not found" in str(exc.value)


@respx.mock
async def test_retries_on_429_then_succeeds():
    route = respx.get(f"{BASE}/crm/v3/owners").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}, json={"message": "rate"}),
            httpx.Response(200, json={"results": [{"id": "1"}]}),
        ]
    )
    client = make_client()
    try:
        result = await client.request("GET", "/crm/v3/owners")
    finally:
        await client.aclose()

    assert result == {"results": [{"id": "1"}]}
    assert route.call_count == 2


@respx.mock
async def test_upload_sends_multipart_and_bearer():
    route = respx.post(f"{BASE}/files/v3/files").mock(
        return_value=httpx.Response(201, json={"id": "9"})
    )
    client = make_client()
    try:
        result = await client.upload(
            "/files/v3/files",
            files={"file": ("a.bin", b"\x00\x01\x02", "application/octet-stream")},
            data={"options": '{"access":"PRIVATE"}', "folderPath": "/"},
        )
    finally:
        await client.aclose()

    assert result == {"id": "9"}
    req = route.calls.last.request
    assert req.headers["content-type"].startswith("multipart/form-data; boundary=")
    assert req.headers["Authorization"] == "Bearer tok"
    assert b'filename="a.bin"' in req.content


@respx.mock
async def test_upload_429_raises_and_posts_once():
    route = respx.post(f"{BASE}/files/v3/files").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "0"}, json={"message": "rate"})
    )
    client = make_client()
    try:
        with pytest.raises(HubSpotError) as exc:
            await client.upload(
                "/files/v3/files",
                files={"file": ("a.bin", b"x", "application/octet-stream")},
            )
    finally:
        await client.aclose()

    assert exc.value.status_code == 429
    assert route.call_count == 1
