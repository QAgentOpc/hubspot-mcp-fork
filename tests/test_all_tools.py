"""Endpoint coverage for every registered tool.

Each tool is invoked through the in-memory FastMCP client with a respx catch-all
mocking ``api.hubapi.com``. We assert the tool issued the expected HTTP method +
path (and, for the key mutating tools, the expected request body). This guards
against endpoint typos and payload-shape regressions across all 76 tools without
touching the real HubSpot API.
"""

import json
import re

import httpx
import pytest
import respx
from fastmcp import Client

BASE = "https://api.hubapi.com"


@pytest.fixture
def server():
    import hubspot_mcp.server as srv

    srv._client = None
    return srv


# Body assertions for the higher-risk mutating tools.
def _check(fn):
    return fn


# (tool, args, method, expected_path, body_check|None)
CASES = [
    # ---- CRM objects ----
    ("hubspot_list_objects", {"object_type": "contacts"}, "GET", "/crm/v3/objects/contacts", None),
    ("hubspot_get_object", {"object_type": "contacts", "object_id": "123"}, "GET", "/crm/v3/objects/contacts/123", None),
    ("hubspot_create_object", {"object_type": "contacts", "properties": {"email": "a@b.com"}}, "POST", "/crm/v3/objects/contacts",
     _check(lambda b: b == {"properties": {"email": "a@b.com"}})),
    ("hubspot_update_object", {"object_type": "contacts", "object_id": "123", "properties": {"firstname": "Ada"}}, "PATCH", "/crm/v3/objects/contacts/123",
     _check(lambda b: b["properties"]["firstname"] == "Ada")),
    ("hubspot_delete_object", {"object_type": "contacts", "object_id": "123"}, "DELETE", "/crm/v3/objects/contacts/123", None),
    ("hubspot_search_objects", {"object_type": "contacts", "query": "ada", "limit": 5}, "POST", "/crm/v3/objects/contacts/search",
     _check(lambda b: b["query"] == "ada" and b["limit"] == 5)),
    ("hubspot_batch_read_objects", {"object_type": "contacts", "ids": ["1", "2"]}, "POST", "/crm/v3/objects/contacts/batch/read",
     _check(lambda b: b["inputs"] == [{"id": "1"}, {"id": "2"}])),
    # ---- Properties ----
    ("hubspot_list_properties", {"object_type": "contacts"}, "GET", "/crm/v3/properties/contacts", None),
    ("hubspot_get_property", {"object_type": "contacts", "property_name": "email"}, "GET", "/crm/v3/properties/contacts/email", None),
    ("hubspot_create_property", {"object_type": "contacts", "name": "f", "label": "F", "type": "string", "field_type": "text"}, "POST", "/crm/v3/properties/contacts",
     _check(lambda b: b["name"] == "f" and b["fieldType"] == "text")),
    # ---- Associations ----
    ("hubspot_list_associations", {"object_type": "contacts", "object_id": "1", "to_object_type": "companies"}, "GET", "/crm/v4/objects/contacts/1/associations/companies", None),
    ("hubspot_associate_default", {"from_object_type": "contacts", "from_object_id": "1", "to_object_type": "companies", "to_object_id": "2"}, "PUT", "/crm/v4/objects/contacts/1/associations/default/companies/2", None),
    ("hubspot_associate_labeled", {"from_object_type": "contacts", "from_object_id": "1", "to_object_type": "companies", "to_object_id": "2", "association_types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 1}]}, "PUT", "/crm/v4/objects/contacts/1/associations/companies/2",
     _check(lambda b: b[0]["associationTypeId"] == 1)),
    ("hubspot_delete_association", {"from_object_type": "contacts", "from_object_id": "1", "to_object_type": "companies", "to_object_id": "2"}, "DELETE", "/crm/v4/objects/contacts/1/associations/companies/2", None),
    ("hubspot_list_association_labels", {"from_object_type": "contacts", "to_object_type": "companies"}, "GET", "/crm/associations/v4/contacts/companies/labels", None),
    # ---- Owners ----
    ("hubspot_list_owners", {}, "GET", "/crm/v3/owners", None),
    ("hubspot_get_owner", {"owner_id": "55"}, "GET", "/crm/v3/owners/55", None),
    # ---- Pipelines ----
    ("hubspot_list_pipelines", {"object_type": "deals"}, "GET", "/crm/v3/pipelines/deals", None),
    ("hubspot_get_pipeline", {"object_type": "deals", "pipeline_id": "default"}, "GET", "/crm/v3/pipelines/deals/default", None),
    ("hubspot_list_pipeline_stages", {"object_type": "deals", "pipeline_id": "default"}, "GET", "/crm/v3/pipelines/deals/default/stages", None),
    # ---- Engagements ----
    ("hubspot_create_note", {"body": "hi"}, "POST", "/crm/v3/objects/notes",
     _check(lambda b: b["properties"]["hs_note_body"] == "hi" and "hs_timestamp" in b["properties"])),
    ("hubspot_create_task", {"subject": "do it"}, "POST", "/crm/v3/objects/tasks",
     _check(lambda b: b["properties"]["hs_task_subject"] == "do it" and "hs_timestamp" in b["properties"])),
    # ---- Lists ----
    ("hubspot_create_list", {"name": "L"}, "POST", "/crm/v3/lists",
     _check(lambda b: b["name"] == "L" and b["objectTypeId"] == "0-1" and b["processingType"] == "MANUAL")),
    ("hubspot_get_list", {"list_id": "99"}, "GET", "/crm/v3/lists/99", None),
    ("hubspot_search_lists", {"query": "vip"}, "POST", "/crm/v3/lists/search",
     _check(lambda b: b["query"] == "vip")),
    ("hubspot_delete_list", {"list_id": "99"}, "DELETE", "/crm/v3/lists/99", None),
    ("hubspot_get_list_memberships", {"list_id": "99"}, "GET", "/crm/v3/lists/99/memberships", None),
    ("hubspot_add_list_members", {"list_id": "99", "record_ids": ["1", "2"]}, "PUT", "/crm/v3/lists/99/memberships/add",
     _check(lambda b: b == ["1", "2"])),
    ("hubspot_remove_list_members", {"list_id": "99", "record_ids": ["1"]}, "PUT", "/crm/v3/lists/99/memberships/remove",
     _check(lambda b: b == ["1"])),
    # ---- Campaigns ----
    ("hubspot_list_campaigns", {}, "GET", "/marketing/v3/campaigns", None),
    ("hubspot_get_campaign", {"campaign_guid": "g1"}, "GET", "/marketing/v3/campaigns/g1", None),
    ("hubspot_create_campaign", {"properties": {"hs_name": "Launch"}}, "POST", "/marketing/v3/campaigns",
     _check(lambda b: b == {"properties": {"hs_name": "Launch"}})),
    ("hubspot_update_campaign", {"campaign_guid": "g1", "properties": {"hs_name": "X"}}, "PATCH", "/marketing/v3/campaigns/g1",
     _check(lambda b: b["properties"]["hs_name"] == "X")),
    ("hubspot_delete_campaign", {"campaign_guid": "g1"}, "DELETE", "/marketing/v3/campaigns/g1", None),
    ("hubspot_list_campaign_asset_types", {}, "GET", "/marketing/campaigns/v3/asset-types", None),
    ("hubspot_list_campaign_assets", {"campaign_guid": "g1", "asset_type": "EMAIL"}, "GET", "/marketing/v3/campaigns/g1/assets/EMAIL", None),
    ("hubspot_add_campaign_asset", {"campaign_guid": "g1", "asset_type": "EMAIL", "asset_id": "5"}, "PUT", "/marketing/v3/campaigns/g1/assets/EMAIL/5", None),
    ("hubspot_remove_campaign_asset", {"campaign_guid": "g1", "asset_type": "EMAIL", "asset_id": "5"}, "DELETE", "/marketing/v3/campaigns/g1/assets/EMAIL/5", None),
    ("hubspot_get_campaign_metrics", {"campaign_guid": "g1"}, "GET", "/marketing/v3/campaigns/g1/reports/metrics", None),
    ("hubspot_get_campaign_revenue", {"campaign_guid": "g1"}, "GET", "/marketing/v3/campaigns/g1/reports/revenue", None),
    ("hubspot_get_campaign_contacts", {"campaign_guid": "g1", "contact_type": "influenced"}, "GET", "/marketing/v3/campaigns/g1/reports/contacts/influenced", None),
    # ---- Marketing emails ----
    ("hubspot_list_marketing_emails", {}, "GET", "/marketing/v3/emails", None),
    ("hubspot_get_marketing_email", {"email_id": "77"}, "GET", "/marketing/v3/emails/77", None),
    ("hubspot_create_marketing_email", {"name": "E", "subject": "S"}, "POST", "/marketing/v3/emails",
     _check(lambda b: b["name"] == "E" and b["subject"] == "S")),
    ("hubspot_update_marketing_email", {"email_id": "77", "updates": {"name": "E2"}}, "PATCH", "/marketing/v3/emails/77",
     _check(lambda b: b == {"name": "E2"})),
    ("hubspot_delete_marketing_email", {"email_id": "77"}, "DELETE", "/marketing/v3/emails/77", None),
    ("hubspot_clone_marketing_email", {"email_id": "77", "clone_name": "copy"}, "POST", "/marketing/v3/emails/clone",
     _check(lambda b: b["id"] == "77" and b["cloneName"] == "copy")),
    ("hubspot_publish_marketing_email", {"email_id": "77"}, "POST", "/marketing/v3/emails/77/publish", None),
    ("hubspot_unpublish_marketing_email", {"email_id": "77"}, "POST", "/marketing/v3/emails/77/unpublish", None),
    ("hubspot_get_marketing_email_statistics", {}, "GET", "/marketing/v3/emails/statistics/list", None),
    # ---- Email send ----
    ("hubspot_send_transactional_email", {"email_id": 1, "to": "a@b.com"}, "POST", "/marketing/v3/transactional/single-email/send",
     _check(lambda b: b["emailId"] == 1 and b["message"]["to"] == "a@b.com")),
    ("hubspot_send_marketing_email", {"email_id": 1, "to": "a@b.com"}, "POST", "/marketing/v4/email/single-send",
     _check(lambda b: b["emailId"] == 1 and b["message"]["to"] == "a@b.com")),
    # ---- Forms ----
    ("hubspot_list_forms", {}, "GET", "/marketing/v3/forms", None),
    ("hubspot_get_form", {"form_id": "f1"}, "GET", "/marketing/v3/forms/f1", None),
    ("hubspot_create_form", {"form_definition": {"name": "Contact"}}, "POST", "/marketing/v3/forms",
     _check(lambda b: b == {"name": "Contact"})),
    ("hubspot_update_form", {"form_id": "f1", "updates": {"name": "C2"}}, "PATCH", "/marketing/v3/forms/f1",
     _check(lambda b: b == {"name": "C2"})),
    ("hubspot_delete_form", {"form_id": "f1"}, "DELETE", "/marketing/v3/forms/f1", None),
    # ---- Marketing events ----
    ("hubspot_list_marketing_events", {}, "GET", "/marketing/marketing-events/v3", None),
    ("hubspot_search_marketing_events", {"q": "webinar"}, "GET", "/marketing/v3/marketing-events/events/search", None),
    ("hubspot_get_marketing_event", {"object_id": "oid"}, "GET", "/marketing/v3/marketing-events/oid", None),
    ("hubspot_upsert_marketing_events", {"inputs": [{"externalEventId": "e1", "eventName": "W"}]}, "POST", "/marketing/v3/marketing-events/events/upsert",
     _check(lambda b: b["inputs"][0]["externalEventId"] == "e1")),
    ("hubspot_update_marketing_event", {"object_id": "oid", "properties": {"eventName": "W2"}}, "PATCH", "/marketing/v3/marketing-events/oid",
     _check(lambda b: b == {"eventName": "W2"})),
    ("hubspot_delete_marketing_event", {"object_id": "oid"}, "DELETE", "/marketing/v3/marketing-events/oid", None),
    ("hubspot_cancel_marketing_event", {"external_event_id": "e1"}, "POST", "/marketing/v3/marketing-events/events/e1/cancel", None),
    ("hubspot_record_marketing_event_attendance", {"object_id": "oid", "subscriber_state": "ATTENDED", "contacts": [{"email": "a@b.com"}]}, "POST", "/marketing/v3/marketing-events/oid/attendance/ATTENDED/create",
     _check(lambda b: b["inputs"][0]["email"] == "a@b.com")),
    # ---- Subscriptions ----
    ("hubspot_list_subscription_definitions", {}, "GET", "/communication-preferences/v3/definitions", None),
    ("hubspot_get_subscription_status", {"email": "a@b.com"}, "GET", r"/communication-preferences/v3/status/email/.+", None),
    ("hubspot_subscribe", {"email": "a@b.com", "subscription_id": "5"}, "POST", "/communication-preferences/v3/subscribe",
     _check(lambda b: b["emailAddress"] == "a@b.com" and b["subscriptionId"] == "5")),
    ("hubspot_unsubscribe", {"email": "a@b.com", "subscription_id": "5"}, "POST", "/communication-preferences/v3/unsubscribe",
     _check(lambda b: b["emailAddress"] == "a@b.com" and b["subscriptionId"] == "5")),
    # ---- Automation ----
    ("hubspot_list_flows", {}, "GET", "/automation/v4/flows", None),
    ("hubspot_get_flow", {"flow_id": "fl1"}, "GET", "/automation/v4/flows/fl1", None),
    ("hubspot_get_flow_performance", {"flow_id": "fl1"}, "GET", "/automation/v4/flows/performance/fl1", None),
    ("hubspot_list_email_campaign_flows", {}, "GET", "/automation/v4/flows/email-campaigns", None),
    # ---- Account / schemas ----
    # ---- Files ----
    ("hubspot_upload_file", {"filename": "a.txt", "data_base64": "aGk="}, "POST", "/files/v3/files", None),
    ("hubspot_attach_file_to_deal", {"deal_id": "5", "filename": "a.txt", "data_base64": "aGk="}, "POST", "/crm/v3/objects/notes", None),
    ("hubspot_get_file", {"file_id": "1"}, "GET", "/files/v3/files/1", None),
    ("hubspot_get_file_signed_url", {"file_id": "1"}, "GET", "/files/v3/files/1/signed-url", None),
    ("hubspot_download_file", {"file_id": "1"}, "GET", "/files/v3/files/1/signed-url", None),
    # ---- Account / schemas ----
    ("hubspot_get_account_details", {}, "GET", "/account-info/v3/details", None),
    ("hubspot_list_object_schemas", {}, "GET", "/crm-object-schemas/v3/schemas", None),
    ("hubspot_get_object_schema", {"object_type": "contacts"}, "GET", "/crm-object-schemas/v3/schemas/contacts", None),
]


def test_every_registered_tool_has_a_case():
    """Ensure this table stays exhaustive as tools are added."""
    import asyncio

    import hubspot_mcp.server as srv

    # asyncio.get_event_loop() raises on 3.12+ when no loop is running; this is
    # a sync test, so run the coroutine on a fresh loop.
    registered = {t.name for t in asyncio.run(srv.mcp.list_tools())}
    covered = {c[0] for c in CASES}
    missing = registered - covered
    assert not missing, f"tools without an endpoint test: {sorted(missing)}"


@pytest.mark.parametrize("tool,args,method,path,body_check", CASES, ids=[c[0] for c in CASES])
@respx.mock
async def test_tool_hits_expected_endpoint(server, tool, args, method, path, body_check):
    route = respx.route().mock(
        return_value=httpx.Response(
            200,
            json={"id": "1", "results": [], "paging": {}, "properties": {}, "inputs": [], "url": "https://files.example/signed"},
        )
    )
    async with Client(server.mcp) as client:
        await client.call_tool(tool, args)

    matches = [
        c
        for c in route.calls
        if c.request.method == method and re.fullmatch(path, c.request.url.path)
    ]
    assert matches, (
        f"{tool}: expected {method} {path}; got "
        f"{[(c.request.method, c.request.url.path) for c in route.calls]}"
    )
    if body_check is not None:
        body = json.loads(matches[0].request.content or b"{}")
        assert body_check(body), f"{tool}: body assertion failed for {body}"
