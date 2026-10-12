#!/usr/bin/env python
"""One-shot MCP CLI for the agents endpoint (runs inside the container).

Usage:
    hubspot-cli tools
    hubspot-cli call <tool_name> '<json-args>'

Examples:
    hubspot-cli call hubspot_search_objects '{"object_type":"contacts","query":"ada"}'
    hubspot-cli call hubspot_get_object '{"object_type":"companies","object_id":"123"}'
"""

from __future__ import annotations

import json
import sys

from fastmcp import Client

SERVER = "http://127.0.0.1:8000/mcp"


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ("tools", "call"):
        print(__doc__, file=sys.stderr)
        return 2

    with Client(SERVER) as client:
        if sys.argv[1] == "tools":
            tools = client.list_tools()
            for t in tools:
                print(t.name)
            return 0

        if len(sys.argv) != 4:
            print("usage: hubspot-cli call <tool_name> '<json-args>'", file=sys.stderr)
            return 2
        tool, raw_args = sys.argv[2], sys.argv[3]
        try:
            args = json.loads(raw_args)
        except json.JSONDecodeError as exc:
            print(f"invalid JSON args: {exc}", file=sys.stderr)
            return 2

        result = client.call_tool(tool, args)
        for block in result.content:
            if getattr(block, "type", "") == "text":
                print(block.text)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
