"""Engagement convenience tools (notes and tasks).

Notes and tasks are CRM objects, so they could be created with the generic
``hubspot_create_object`` tool — but they require a few specific properties and
are almost always linked to a contact/company/deal. These helpers fill in the
required ``hs_timestamp`` and wire up associations for you.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ._base import ClientGetter, api


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


async def _associate_all(
    get_client: ClientGetter,
    from_object_type: str,
    from_id: str,
    associations: list[dict[str, str]] | None,
) -> list[dict[str, str]]:
    """Create default associations from a new engagement to other records."""

    linked: list[dict[str, str]] = []
    for assoc in associations or []:
        to_type = assoc.get("to_object_type") or assoc.get("toObjectType")
        to_id = assoc.get("to_object_id") or assoc.get("toObjectId")
        if not to_type or not to_id:
            continue
        await api(
            get_client,
            "PUT",
            f"/crm/v4/objects/{from_object_type}/{from_id}"
            f"/associations/default/{to_type}/{to_id}",
        )
        linked.append({"to_object_type": to_type, "to_object_id": to_id})
    return linked


def register(mcp, get_client: ClientGetter) -> None:
    @mcp.tool()
    async def hubspot_create_note(
        body: str,
        associations: list[dict[str, str]] | None = None,
        owner_id: str | None = None,
        timestamp: str | None = None,
        attachment_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a note, optionally linked to other records.

        Args:
            body: The note text (plain text or simple HTML).
            associations: Records to attach the note to, each
                {"to_object_type": "contacts", "to_object_id": "123"}.
            owner_id: Optional owner (hubspot_owner_id) for the note.
            timestamp: ISO-8601 time the note occurred. Defaults to now.
            attachment_ids: Optional IDs of files (from hubspot_upload_file) to
                attach to the note.

        Returns:
            The created note, plus the list of associations that were linked.
        """

        properties: dict[str, Any] = {
            "hs_note_body": body,
            "hs_timestamp": timestamp or _now_iso(),
        }
        if owner_id is not None:
            properties["hubspot_owner_id"] = owner_id
        if attachment_ids:
            properties["hs_attachment_ids"] = ";".join(str(a) for a in attachment_ids)
        note = await api(
            get_client, "POST", "/crm/v3/objects/notes", json={"properties": properties}
        )
        linked = await _associate_all(get_client, "notes", note["id"], associations)
        return {"note": note, "associations": linked}

    @mcp.tool()
    async def hubspot_create_task(
        subject: str,
        body: str | None = None,
        status: str = "NOT_STARTED",
        priority: str | None = None,
        due_date: str | None = None,
        associations: list[dict[str, str]] | None = None,
        owner_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a task, optionally linked to other records.

        Args:
            subject: Task title.
            body: Optional task notes/body.
            status: One of NOT_STARTED, IN_PROGRESS, WAITING, COMPLETED, DEFERRED.
            priority: Optional: NONE, LOW, MEDIUM, HIGH.
            due_date: ISO-8601 due date/time. Also used as hs_timestamp.
            associations: Records to attach the task to, each
                {"to_object_type": "deals", "to_object_id": "123"}.
            owner_id: Optional owner (hubspot_owner_id) for the task.

        Returns:
            The created task, plus the list of associations that were linked.
        """

        properties: dict[str, Any] = {
            "hs_task_subject": subject,
            "hs_task_status": status,
            "hs_timestamp": due_date or _now_iso(),
        }
        if body is not None:
            properties["hs_task_body"] = body
        if priority is not None:
            properties["hs_task_priority"] = priority
        if owner_id is not None:
            properties["hubspot_owner_id"] = owner_id
        task = await api(
            get_client, "POST", "/crm/v3/objects/tasks", json={"properties": properties}
        )
        linked = await _associate_all(get_client, "tasks", task["id"], associations)
        return {"task": task, "associations": linked}
