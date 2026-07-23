"""File tools (HubSpot Files API v3) and file-backed notes.

The generic object tools can't upload binary files: the Files API takes a
``multipart/form-data`` body, not JSON. These helpers upload a file — provided
as base64, since MCP tool arguments are JSON — and, for the common case, attach
it to a deal as a note in a single call.
"""

from __future__ import annotations

import base64
import binascii
import json
import mimetypes
from datetime import datetime, timezone
from typing import Any

import httpx

from ._base import ClientGetter, ToolError, api, upload

# HubSpot file visibility values accepted by the Files API ``options.access``.
_ACCESS_VALUES = {
    "PRIVATE",
    "PUBLIC_INDEXABLE",
    "PUBLIC_NOT_INDEXABLE",
    "HIDDEN_INDEXABLE",
    "HIDDEN_NOT_INDEXABLE",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _decode_b64(data_base64: str) -> bytes:
    try:
        return base64.b64decode(data_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ToolError(f"data_base64 is not valid base64: {exc}") from exc


def _check_access(access: str) -> None:
    if access not in _ACCESS_VALUES:
        raise ToolError(
            f"access must be one of {sorted(_ACCESS_VALUES)}, got {access!r}"
        )


async def _fetch_signed_url(get_client: ClientGetter, file_id: str) -> str:
    """Ask HubSpot for a short-lived signed URL to download a file's bytes.

    Private files aren't served from their plain ``url`` (that redirects to a
    login); the Files API mints a temporary signed URL instead.
    """
    resp = await api(
        get_client, "GET", f"/files/v3/files/{file_id}/signed-url"
    )
    url = resp.get("url") if isinstance(resp, dict) else None
    if not url:
        raise ToolError(f"HubSpot returned no signed URL for file {file_id}")
    return url


async def _do_upload(
    get_client: ClientGetter,
    filename: str,
    raw: bytes,
    folder_path: str,
    access: str,
) -> dict[str, Any]:
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return await upload(
        get_client,
        "/files/v3/files",
        files={"file": (filename, raw, content_type)},
        data={"options": json.dumps({"access": access}), "folderPath": folder_path},
    )


def register(mcp, get_client: ClientGetter) -> None:
    @mcp.tool()
    async def hubspot_upload_file(
        filename: str,
        data_base64: str,
        folder_path: str = "/",
        access: str = "PRIVATE",
    ) -> dict[str, Any]:
        """Upload a file to the HubSpot file manager.

        The generic object tools can't do this — file bytes need a multipart
        upload, so the content is passed here as base64.

        Args:
            filename: Name to store the file under (its extension sets the type).
            data_base64: The file's bytes, base64-encoded.
            folder_path: Destination folder path (default root "/").
            access: File visibility — PRIVATE (default), PUBLIC_INDEXABLE,
                PUBLIC_NOT_INDEXABLE, HIDDEN_INDEXABLE, HIDDEN_NOT_INDEXABLE.

        Returns:
            The uploaded file object, including its ``id`` and ``url``.
        """

        _check_access(access)
        raw = _decode_b64(data_base64)
        return await _do_upload(get_client, filename, raw, folder_path, access)

    @mcp.tool()
    async def hubspot_attach_file_to_deal(
        deal_id: str,
        filename: str,
        data_base64: str,
        note_body: str | None = None,
        access: str = "PRIVATE",
        folder_path: str = "/",
        owner_id: str | None = None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        """Upload a file and attach it to a deal as a note.

        Uploads the file, creates a note carrying it as an attachment, and links
        the note to the deal — the one-call path for "add this file to a deal".

        Args:
            deal_id: The deal (object) ID to attach the file to.
            filename: Name to store the file under.
            data_base64: The file's bytes, base64-encoded.
            note_body: Optional note text shown with the attachment. Defaults to
                a short "Attached file: <name>" line.
            access: File visibility (see hubspot_upload_file). Default PRIVATE.
            folder_path: Destination folder path (default root "/").
            owner_id: Optional owner (hubspot_owner_id) for the note.
            timestamp: ISO-8601 time for the note. Defaults to now.

        Returns:
            The uploaded ``file`` and the created ``note``.
        """

        _check_access(access)
        raw = _decode_b64(data_base64)
        uploaded = await _do_upload(get_client, filename, raw, folder_path, access)

        properties: dict[str, Any] = {
            "hs_note_body": note_body or f"Attached file: {filename}",
            "hs_timestamp": timestamp or _now_iso(),
            "hs_attachment_ids": str(uploaded["id"]),
        }
        if owner_id is not None:
            properties["hubspot_owner_id"] = owner_id
        note = await api(
            get_client, "POST", "/crm/v3/objects/notes", json={"properties": properties}
        )
        await api(
            get_client,
            "PUT",
            f"/crm/v4/objects/notes/{note['id']}/associations/default/deals/{deal_id}",
        )
        return {"file": uploaded, "note": note}

    @mcp.tool()
    async def hubspot_get_file(file_id: str) -> dict[str, Any]:
        """Get a file's metadata (name, extension, type, size, url).

        The generic ``hubspot_get_object`` rejects file objects
        ("FILE_MANAGER_FILE not supported"); use this to inspect a file you
        found via a note's ``hs_attachment_ids``.

        Args:
            file_id: The HubSpot file ID.

        Returns:
            The file object.
        """

        return await api(get_client, "GET", f"/files/v3/files/{file_id}")

    @mcp.tool()
    async def hubspot_get_file_signed_url(file_id: str) -> dict[str, Any]:
        """Get a short-lived signed URL to download a file.

        Useful to hand a downloadable link to the user; the URL expires. For
        the bytes directly, use ``hubspot_download_file``.

        Args:
            file_id: The HubSpot file ID.

        Returns:
            ``{"file_id", "url"}`` — the temporary signed download URL.
        """

        url = await _fetch_signed_url(get_client, file_id)
        return {"file_id": file_id, "url": url}

    @mcp.tool()
    async def hubspot_download_file(file_id: str) -> dict[str, Any]:
        """Download a file's bytes.

        Fetches a signed URL and downloads the content, returning it as base64
        (MCP results are JSON) — the read side of ``hubspot_upload_file``, and
        what lets you actually open a note's attachment.

        Args:
            file_id: The HubSpot file ID (e.g. from a note's hs_attachment_ids).

        Returns:
            ``{"id", "name", "extension", "type", "size", "data_base64"}``.
        """

        meta = await api(get_client, "GET", f"/files/v3/files/{file_id}")
        url = await _fetch_signed_url(get_client, file_id)
        # The signed URL is pre-authenticated (and on a CDN host), so fetch it
        # without the HubSpot bearer; follow the redirect to the storage blob.
        try:
            async with httpx.AsyncClient(
                timeout=60.0, follow_redirects=True
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                raw = resp.content
        except httpx.HTTPError as exc:
            raise ToolError(f"downloading file {file_id} failed: {exc}") from exc

        meta = meta if isinstance(meta, dict) else {}
        return {
            "id": file_id,
            "name": meta.get("name"),
            "extension": meta.get("extension"),
            "type": meta.get("type"),
            "size": meta.get("size"),
            "data_base64": base64.b64encode(raw).decode(),
        }
