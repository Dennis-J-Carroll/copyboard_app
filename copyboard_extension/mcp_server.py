#!/usr/bin/env python3
"""
Copyboard MCP Server – Exposes Copyboard as tools and resources
for AI coding agents via the Model Context Protocol.

Requires the optional `mcp` package:
    pip install copyboard-extension[agent]

Launch:
    python -m copyboard_extension.mcp_server

Configure in Claude Desktop (claude_desktop_config.json):
    {
      "mcpServers": {
        "copyboard": {
          "command": "python",
          "args": ["-m", "copyboard_extension.mcp_server"]
        }
      }
    }
"""

import json
import sys

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        Tool,
        TextContent,
        Resource,
    )
    HAS_MCP = True
except ImportError:
    HAS_MCP = False

from .agent_api import (
    get_profile,
    fire_snippet,
    fire_by_label,
    search_snippets,
    get_chambers,
    get_top_snippets,
    add_snippet,
    add_chamber,
    remove_snippet,
    get_board,
    add_to_board,
    describe,
)


def create_server() -> "Server":
    """Create and configure the MCP server."""
    if not HAS_MCP:
        raise ImportError(
            "The 'mcp' package is required for the Copyboard MCP server.\n"
            "Install it with: pip install mcp\n"
            "Or: pip install copyboard-extension[agent]"
        )

    server = Server("copyboard")

    # ── Resources ────────────────────────────────────────────────────

    @server.list_resources()
    async def list_resources():
        return [
            Resource(
                uri="copyboard://profile",
                name="Coding Profile",
                description="Auto-generated coding fingerprint from the user's Copyboard usage patterns",
                mimeType="application/json",
            ),
            Resource(
                uri="copyboard://snippets",
                name="Snippet Chambers",
                description="All available code snippet chambers and their contents",
                mimeType="application/json",
            ),
            Resource(
                uri="copyboard://board",
                name="Clipboard Board",
                description="Current clipboard board contents",
                mimeType="application/json",
            ),
        ]

    @server.read_resource()
    async def read_resource(uri: str):
        if uri == "copyboard://profile":
            return json.dumps(get_profile(), indent=2)
        elif uri == "copyboard://snippets":
            return json.dumps(get_chambers(), indent=2)
        elif uri == "copyboard://board":
            return json.dumps(get_board(), indent=2)
        else:
            raise ValueError(f"Unknown resource: {uri}")

    # ── Tools ────────────────────────────────────────────────────────

    @server.list_tools()
    async def list_tools():
        return [
            Tool(
                name="get_profile",
                description=(
                    "Get the user's coding profile — a data-driven fingerprint "
                    "of their coding patterns inferred from Copyboard snippet usage. "
                    "Use this to understand the user's preferred languages, testing "
                    "framework, code style, and workflows."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "as_markdown": {
                            "type": "boolean",
                            "description": "Return as markdown (True) or JSON (False)",
                            "default": False,
                        }
                    },
                },
            ),
            Tool(
                name="fire_snippet",
                description=(
                    "Fire (paste) a code snippet by chamber and snippet index. "
                    "This copies the expanded snippet text to the system clipboard. "
                    "Template variables like ${date}, ${user}, ${project} are expanded automatically."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "chamber": {
                            "type": "integer",
                            "description": "Chamber index (0-based)",
                        },
                        "snippet": {
                            "type": "integer",
                            "description": "Snippet index within chamber (0-based)",
                        },
                        "expand": {
                            "type": "boolean",
                            "description": "Expand template variables",
                            "default": True,
                        },
                    },
                    "required": ["chamber", "snippet"],
                },
            ),
            Tool(
                name="fire_by_label",
                description=(
                    "Fire a snippet by searching for its label name. "
                    "Case-insensitive match across all chambers."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "label": {
                            "type": "string",
                            "description": "Snippet label to search for",
                        },
                    },
                    "required": ["label"],
                },
            ),
            Tool(
                name="search_snippets",
                description=(
                    "Search for snippets by keyword across all chambers. "
                    "Matches against both labels and snippet text."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query",
                        },
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="add_snippet",
                description=(
                    "Add a new code snippet to an existing chamber. "
                    "Use ${cursor} in the text to mark where the cursor should be placed."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "chamber": {
                            "type": "integer",
                            "description": "Chamber index to add the snippet to",
                        },
                        "label": {
                            "type": "string",
                            "description": "Human-readable label for the snippet",
                        },
                        "text": {
                            "type": "string",
                            "description": "The snippet text to paste",
                        },
                    },
                    "required": ["chamber", "label", "text"],
                },
            ),
            Tool(
                name="get_board",
                description="Get the current clipboard board contents.",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="add_to_board",
                description="Add text to the clipboard board.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to add to the clipboard board",
                        },
                    },
                    "required": ["text"],
                },
            ),
            Tool(
                name="list_chambers",
                description="List all available snippet chambers with their snippet counts.",
                inputSchema={"type": "object", "properties": {}},
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        if name == "get_profile":
            result = get_profile(as_markdown=arguments.get("as_markdown", False))
            text = result if isinstance(result, str) else json.dumps(result, indent=2)
            return [TextContent(type="text", text=text)]

        elif name == "fire_snippet":
            result = fire_snippet(
                arguments["chamber"],
                arguments["snippet"],
                expand=arguments.get("expand", True),
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "fire_by_label":
            result = fire_by_label(arguments["label"])
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "search_snippets":
            result = search_snippets(arguments["query"])
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "add_snippet":
            result = add_snippet(
                arguments["chamber"],
                arguments["label"],
                arguments["text"],
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_board":
            result = get_board()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "add_to_board":
            result = add_to_board(arguments["text"])
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "list_chambers":
            chambers = get_chambers()
            summary = [
                {"index": i, "name": c["name"], "icon": c.get("icon", ""),
                 "snippets": len(c.get("snippets", []))}
                for i, c in enumerate(chambers)
            ]
            return [TextContent(type="text", text=json.dumps(summary, indent=2))]

        else:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    return server


async def main():
    """Run the MCP server over stdio."""
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    if not HAS_MCP:
        print("Error: The 'mcp' package is required.")
        print("Install it with: pip install mcp")
        sys.exit(1)

    import asyncio
    asyncio.run(main())
