# hubspot-mcp

A [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server for the
[HubSpot CRM API](https://developers.hubspot.com/docs/api-reference/latest/overview),
written in Python with [FastMCP](https://github.com/jlowin/fastmcp). It supports
per-user **OAuth** (browser login, multi-user) for remote deployments, or a
single static token for local use.

It's built for **marketing automation**: managing campaigns, marketing emails,
forms, lists, subscriptions, and automation flows — on top of full CRM access.
CRM data is reached through **generic, object-typed tools** rather than one tool
per endpoint, so the same six tools work across contacts, companies, deals,
tickets, line items, products, quotes, engagements, and custom objects.

76 tools across CRM and Marketing.

## Features / tools

### CRM

| Area | Tools |
|------|-------|
| **Objects** | `hubspot_list_objects`, `hubspot_get_object`, `hubspot_create_object`, `hubspot_update_object`, `hubspot_delete_object`, `hubspot_search_objects`, `hubspot_batch_read_objects` |
| **Properties** | `hubspot_list_properties`, `hubspot_get_property`, `hubspot_create_property` |
| **Associations** (v4) | `hubspot_list_associations`, `hubspot_associate_default`, `hubspot_associate_labeled`, `hubspot_delete_association`, `hubspot_list_association_labels` |
| **Owners** | `hubspot_list_owners`, `hubspot_get_owner` |
| **Pipelines** | `hubspot_list_pipelines`, `hubspot_get_pipeline`, `hubspot_list_pipeline_stages` |
| **Engagements** | `hubspot_create_note`, `hubspot_create_task` |
| **Files** | `hubspot_upload_file`, `hubspot_attach_file_to_deal`, `hubspot_get_file`, `hubspot_get_file_signed_url`, `hubspot_download_file` |
| **Account / schemas** | `hubspot_get_account_details`, `hubspot_list_object_schemas`, `hubspot_get_object_schema` |

### Marketing

| Area | Tools |
|------|-------|
| **Campaigns** | `hubspot_list_campaigns`, `hubspot_get_campaign`, `hubspot_create_campaign`, `hubspot_update_campaign`, `hubspot_delete_campaign`, `hubspot_list_campaign_asset_types`, `hubspot_list_campaign_assets`, `hubspot_add_campaign_asset`, `hubspot_remove_campaign_asset`, `hubspot_get_campaign_metrics`, `hubspot_get_campaign_revenue`, `hubspot_get_campaign_contacts` |
| **Marketing emails** | `hubspot_list_marketing_emails`, `hubspot_get_marketing_email`, `hubspot_create_marketing_email`, `hubspot_update_marketing_email`, `hubspot_delete_marketing_email`, `hubspot_clone_marketing_email`, `hubspot_publish_marketing_email`, `hubspot_unpublish_marketing_email`, `hubspot_get_marketing_email_statistics` |
| **Sending email** | `hubspot_send_transactional_email`, `hubspot_send_marketing_email` |
| **Forms** | `hubspot_list_forms`, `hubspot_get_form`, `hubspot_create_form`, `hubspot_update_form`, `hubspot_delete_form` |
| **Lists** | `hubspot_create_list`, `hubspot_get_list`, `hubspot_search_lists`, `hubspot_delete_list`, `hubspot_get_list_memberships`, `hubspot_add_list_members`, `hubspot_remove_list_members` |
| **Subscriptions** | `hubspot_list_subscription_definitions`, `hubspot_get_subscription_status`, `hubspot_subscribe`, `hubspot_unsubscribe` |
| **Marketing events** | `hubspot_list_marketing_events`, `hubspot_search_marketing_events`, `hubspot_get_marketing_event`, `hubspot_upsert_marketing_events`, `hubspot_update_marketing_event`, `hubspot_delete_marketing_event`, `hubspot_cancel_marketing_event`, `hubspot_record_marketing_event_attendance` |
| **Automation (flows)** | `hubspot_list_flows`, `hubspot_get_flow`, `hubspot_get_flow_performance`, `hubspot_list_email_campaign_flows` |

The generic object tools take an `object_type` argument such as `contacts`,
`companies`, `deals`, `tickets`, `notes`, `tasks`, or a custom object's name /
`objectTypeId` (e.g. `2-12345678`).

## Authentication

The server supports two modes:

- **`oauth` (recommended, multi-user)** — runs as a **remote HTTP server**.
  Each user signs in to HubSpot through their browser, driven by the MCP client
  (Claude opens the consent page, captures the token on redirect, and sends it
  as a Bearer token). The server is a [FastMCP `OAuthProxy`](https://gofastmcp.com/servers/auth/oauth-proxy)
  in front of HubSpot's OAuth — necessary because HubSpot doesn't support
  Dynamic Client Registration, while MCP clients expect it. Each user's HubSpot
  token is used per request, so coworkers see only their own HubSpot data.
- **`token` (simple, single-user)** — runs over **stdio** with one static
  HubSpot **private app** token for all requests. Good for local development.

The mode is set by `HUBSPOT_AUTH_MODE`, or inferred: `oauth` if
`HUBSPOT_CLIENT_ID` is set, otherwise `token`.

### OAuth mode — create a HubSpot public app

1. In your **HubSpot developer account** create (or open) an **app**, then go to
   the **Auth** tab. (This is a developer-account *public app* with OAuth — not
   the same as a Settings → Private App.)
2. Copy the **Client ID** and **Client secret**.
3. Add a **Redirect URL**: `<HUBSPOT_SERVER_URL>/auth/callback`
   (e.g. `https://hubspot-mcp.example.com/auth/callback`). `https` is required
   in production; `http://localhost:PORT/auth/callback` is allowed for local dev.
4. On the **Scopes** tab, enable the scopes you need (see below). They must match
   `HUBSPOT_SCOPES` (or the defaults).

### Token mode — create a private app

1. In HubSpot go to **Settings → Integrations → Private Apps → Create**.
2. Grant scopes on the **Scopes** tab and copy the **access token** (`pat-na1-…`).

### Scopes for marketing automation

These are the defaults (`DEFAULT_SCOPES` in `config.py`), derived from the OAuth
scopes declared in HubSpot's official OpenAPI specs. **Every scope you request
must also be enabled on the HubSpot app** — if the app marks a scope *required*
that the request omits, authorization fails with "provided scopes are missing".

| Scope | Tools / API it unlocks |
|-------|------------------------|
| `crm.objects.contacts.read` / `.write` | contacts via object tools; also notes & tasks engagements |
| `crm.objects.companies.read` / `.write` | companies |
| `crm.objects.deals.read` / `.write` | deals |
| `crm.objects.products.read` / `.write` | products / line items |
| `tickets` | ticket records |
| `files` | file upload / download / deal-attachment tools |
| `crm.objects.owners.read` | owners tools |
| `crm.schemas.contacts.read` | property / schema reads |
| `crm.lists.read` / `.write` | lists tools |
| `marketing.campaigns.read` / `.write` | campaigns tools — **needs Marketing Hub Pro+** |
| `marketing.campaigns.revenue.read` | `hubspot_get_campaign_revenue` |
| `content` | marketing emails CRUD + statistics |
| `forms` | forms tools |
| `crm.objects.marketing_events.read` / `.write` | marketing events tools |
| `communication_preferences.read` / `.read_write` | subscriptions tools |
| `automation` | workflow / flow tools |
| `automation.sequences.read`, `automation.sequences.enrollments.write` | reserved (no tool yet); kept so requests satisfy the app's required scopes — **needs Sales/Service Pro** |

> Note: scopes depend on the portal's subscription, and **requesting a scope the
> portal can't grant fails the whole authorization**. Several scopes are therefore
> **not** requested by default and must be added via `HUBSPOT_SCOPES` only on a
> portal that has the matching product:
>
> | Opt-in scope | Requires | Unlocks |
> |--------------|----------|---------|
> | `crm.objects.custom.read` / `.write` | Enterprise | custom objects + object-schema tools |
> | `marketing-email` | Marketing Hub (paid) | marketing email publish/unpublish, v4 single-send |
> | `transactional-email` | Transactional Email add-on | transactional single-send |
>
> Also note `marketing.campaigns.*` needs Marketing Hub **Professional+** and
> `content` needs Marketing/Content Hub — these are requested by default but still
> return 403 if the portal lacks the product.

## Prerequisites

- Python 3.10+
- A HubSpot public app (oauth mode) **or** private app token (token mode).

## Installation

```bash
git clone <this-repo> hubspot-mcp
cd hubspot-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e .          # add ".[dev]" for the test dependencies
```

## Configuration

Configured via environment variables (a local `.env` file is loaded
automatically — copy `.env.example` to `.env`):

| Variable | Mode | Default | Description |
|----------|------|---------|-------------|
| `HUBSPOT_AUTH_MODE` | both | inferred | `oauth` or `token`. |
| `HUBSPOT_CLIENT_ID` | oauth | — | HubSpot public-app client id. |
| `HUBSPOT_CLIENT_SECRET` | oauth | — | HubSpot public-app client secret. |
| `HUBSPOT_SERVER_URL` | oauth | — | Public HTTPS base URL of this server. |
| `HUBSPOT_HOST` | oauth | `0.0.0.0` | Bind address. |
| `HUBSPOT_PORT` | oauth | `8000` | Bind port. |
| `HUBSPOT_SCOPES` | oauth | (defaults) | Space/comma-separated scope list. |
| `HUBSPOT_FORWARD_PKCE` | oauth | `false` | Forward PKCE to HubSpot upstream. |
| `HUBSPOT_ACCESS_TOKEN` | token | — | Private-app access token. |
| `HUBSPOT_BASE_URL` | both | `https://api.hubapi.com` | Override API base URL. |
| `HUBSPOT_TIMEOUT` | both | `30` | Per-request timeout (seconds). |

## Running

### OAuth mode (remote HTTP server)

```bash
HUBSPOT_AUTH_MODE=oauth \
HUBSPOT_CLIENT_ID=... HUBSPOT_CLIENT_SECRET=... \
HUBSPOT_SERVER_URL=https://hubspot-mcp.example.com \
python -m hubspot_mcp
```

Serves MCP over Streamable HTTP at `/mcp`, with the OAuth endpoints
(`/.well-known/oauth-authorization-server`, `/authorize`, `/token`, `/register`,
`/auth/callback`) alongside. Terminate TLS in front of it (reverse proxy) so
`HUBSPOT_SERVER_URL` is reachable over `https`.

**Connect Claude Desktop / claude.ai** → add a **custom connector** pointing at
`https://hubspot-mcp.example.com/mcp`. On first use Claude opens the browser,
you log into HubSpot, and the connection completes — no tokens pasted anywhere.

### Token mode (local stdio)

```bash
HUBSPOT_AUTH_MODE=token HUBSPOT_ACCESS_TOKEN=pat-na1-... python -m hubspot_mcp
```

Use with **Claude Code**:

```bash
claude mcp add hubspot --env HUBSPOT_ACCESS_TOKEN=pat-na1-... -- python -m hubspot_mcp
```

Or **Claude Desktop** (`claude_desktop_config.json`, Settings → Developer):

```json
{
  "mcpServers": {
    "hubspot": {
      "command": "/absolute/path/to/hubspot-mcp/.venv/bin/python",
      "args": ["-m", "hubspot_mcp"],
      "env": {
        "HUBSPOT_AUTH_MODE": "token",
        "HUBSPOT_ACCESS_TOKEN": "pat-na1-..."
      }
    }
  }
}
```

### How the OAuth flow works

1. Claude connects to `/mcp` unauthenticated → server returns `401` with a
   `WWW-Authenticate` header pointing at its protected-resource metadata.
2. Claude discovers the authorization server, registers itself (DCR), and opens
   HubSpot's consent screen in the browser (OAuth 2.1 + PKCE).
3. HubSpot redirects back to `/auth/callback`; the proxy exchanges the code for
   the user's HubSpot tokens and hands an access token to Claude.
4. Claude sends that token as `Bearer` on every MCP request; the server
   validates it against HubSpot and uses it for that user's API calls.

> **Token storage:** OAuth client/token state is kept **in-memory** (suited to a
> single VM — no Redis or other service). A server restart simply prompts users
> to re-authenticate. While running, HubSpot access tokens (which expire after
> ~30 min) are refreshed automatically via the stored refresh token.

## Docker

```bash
docker build -t hubspot-mcp .
docker run --rm -p 8000:8000 \
  -e HUBSPOT_AUTH_MODE=oauth \
  -e HUBSPOT_CLIENT_ID=... -e HUBSPOT_CLIENT_SECRET=... \
  -e HUBSPOT_SERVER_URL=https://hubspot-mcp.example.com \
  hubspot-mcp
```

The image runs as a non-root user and serves OAuth/HTTP mode on port 8000. Put a
TLS-terminating reverse proxy in front so `HUBSPOT_SERVER_URL` is reachable over
`https`.

### Health endpoints (Kubernetes)

In oauth/HTTP mode the server exposes two unauthenticated probe endpoints:

- `GET /healthz` — liveness (process is up and serving HTTP).
- `GET /readyz` — readiness (config loaded; no outbound HubSpot call, so HubSpot
  latency or per-user token state can't flip it).

```yaml
livenessProbe:
  httpGet: { path: /healthz, port: 8000 }
  initialDelaySeconds: 5
  periodSeconds: 10
readinessProbe:
  httpGet: { path: /readyz, port: 8000 }
  initialDelaySeconds: 5
  periodSeconds: 10
```

(Token/stdio mode has no HTTP server, so probes apply to oauth deployments.)

### CI / releases

`.github/workflows/docker.yml` runs the test suite, then builds the image and
pushes it to **GitHub Container Registry** (`ghcr.io/<owner>/<repo>`):

| Trigger | Tags pushed |
|---------|-------------|
| **Publish a GitHub Release** (from tag `vX.Y.Z`) | `X.Y.Z`, `X.Y`, `latest` |
| Push to `main` | `edge`, `sha-<commit>` |
| Pull request | *built but not pushed* (validation only) |

So a release produces the user-facing image (`ghcr.io/<owner>/<repo>:latest` and
the versioned tags), while `main` produces `edge` for testing.

No secrets to configure — it authenticates with the built-in `GITHUB_TOKEN`
(the workflow grants `packages: write`).

#### Make the package public (one-time)

GHCR packages are **private** when first created, and GitHub has **no API** for
the workflow to change that. After the first release push, make it public once —
it then stays public for all future pushes:

1. Repo → **Packages** → click the `hubspot-mcp` package.
2. **Package settings** → **Danger Zone** → **Change visibility** → **Public**.

(Also under Package settings, confirm it's linked to this repo so the README and
permissions inherit correctly.)

Pull it:

```bash
docker pull ghcr.io/<owner>/hubspot-mcp:latest
```

## Usage examples (what the model can do)

Marketing automation:

- **Build & run a campaign** → `hubspot_create_campaign`, then
  `hubspot_create_marketing_email` (associate it via `campaign`),
  `hubspot_publish_marketing_email`, and track results with
  `hubspot_get_campaign_metrics` / `hubspot_get_campaign_revenue`.
- **Segment then target** → `hubspot_create_list` (DYNAMIC with a
  `filter_branch`, or MANUAL + `hubspot_add_list_members`), then use the list to
  target a marketing email.
- **Send a transactional email** → `hubspot_send_transactional_email` with
  `email_id`, recipient, and `custom_properties` for merge tokens.
- **Manage consent** → `hubspot_list_subscription_definitions`,
  `hubspot_subscribe` / `hubspot_unsubscribe`, `hubspot_get_subscription_status`.
- **Inspect automation** → `hubspot_list_flows`, `hubspot_get_flow_performance`.

CRM:

- **Find a contact by email** → `hubspot_search_objects` with
  `object_type="contacts"` and a filter
  `{"propertyName": "email", "operator": "EQ", "value": "ada@example.com"}`.
- **Create a deal and link it to a company** → `hubspot_create_object`
  (`object_type="deals"`) then `hubspot_associate_default` from the new deal to
  the company.
- **Log a call note on a contact** → `hubspot_create_note` with
  `associations=[{"to_object_type": "contacts", "to_object_id": "<id>"}]`.
- **Discover writable fields** → `hubspot_list_properties` for the object type.

## Design notes

- **Per-user auth, one shared client.** A single `httpx.AsyncClient` is created
  on first tool use; the Bearer token is resolved *per request* — from the
  authenticated user's OAuth context in oauth mode, or the static token in token
  mode. The 76 tool modules are auth-agnostic.
- **OAuth proxy.** FastMCP's `OAuthProxy` bridges MCP's DCR expectations to
  HubSpot's pre-registered confidential-client flow; opaque HubSpot tokens are
  validated by `HubSpotTokenVerifier` against the token-info endpoint (cached).
- **Resilience.** Requests retry with exponential backoff on HTTP 429 / 5xx and
  honour HubSpot's `Retry-After` header (~100 requests / 10s limit).
- **Clean errors.** API errors are surfaced to the model as a `ToolError` that
  includes the HubSpot message and status code.
- **Endpoints verified** against the official HubSpot OpenAPI specs (CRM v3
  objects/properties/owners/pipelines/schemas, Associations v4, Marketing v3/v4,
  Automation v4).

## Development

```bash
pip install -e ".[dev]"
pytest
```

Tests mock the HubSpot API with [`respx`](https://lundberg.github.io/respx/), so
no network access or real token is required. Coverage:

- **All 76 tools** are exercised through the in-memory FastMCP client and
  asserted to call the correct HubSpot endpoint (method + path), with
  request-body checks on the mutating tools (`tests/test_all_tools.py`). An
  exhaustiveness guard fails the suite if a new tool is added without a test.
- The shared client (param encoding, bearer injection, 429/5xx retry, error
  mapping), the OAuth token verifier, and config modes have dedicated tests.
- These are **mock-only**; validate against a real HubSpot account on deploy.

## Project layout

```
src/hubspot_mcp/
├── __main__.py        # console entry point (http in oauth mode, stdio in token mode)
├── server.py          # FastMCP instance + auth wiring + shared client
├── config.py          # env-based settings (oauth | token modes)
├── auth.py            # HubSpot OAuth proxy + opaque-token verifier
├── client.py          # async HubSpot HTTP client (per-request token, retries, errors)
└── tools/
    ├── objects.py          # generic CRM object CRUD + search + batch read
    ├── properties.py       # property (field) schema tools
    ├── associations.py     # v4 association tools
    ├── owners.py           # owner lookup
    ├── pipelines.py        # pipelines + stages
    ├── engagements.py      # note / task convenience helpers
    ├── lists.py            # CRM lists + memberships
    ├── campaigns.py        # marketing campaigns + reporting
    ├── marketing_emails.py # marketing email CRUD / publish / stats
    ├── email_send.py       # transactional & marketing single-send
    ├── forms.py            # marketing forms
    ├── marketing_events.py # marketing events + attendance
    ├── subscriptions.py    # communication preferences
    ├── automation.py       # automation flows (workflows)
    └── misc.py             # account details + object schema discovery
```

## License

MIT
