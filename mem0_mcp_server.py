"""
Mem0 MCP Server — Local shared memory for AI coding agents.
Agents connect via MCP stdio transport.

Environment Variables:
  OPENROUTER_API_KEY     — Your OpenRouter API key
  MEM0_AGENT_ID          — Agent/user identifier (default: agent-memory)
  MEM0_COLLECTION        — Qdrant collection name (default: agent_memory)
  LLM_MODEL              — OpenRouter model (default: nvidia/nemotron-3-nano-30b-a3b:free)
  OLLAMA_BASE_URL        — Ollama URL (default: http://localhost:11434)
  QDRANT_URL             — Qdrant URL (default: http://localhost:6333)

Run: OPENROUTER_API_KEY=sk-or-v1-... python3 mem0_mcp_server.py
"""
import os
import json
import sqlite3
import logging

# ── Nuclear Fix: patch sqlite3 BEFORE importing mem0 ──────────────────
_orig_connect = sqlite3.connect
def _connect(*args, **kwargs):
    kwargs.setdefault("check_same_thread", False)
    return _orig_connect(*args, **kwargs)
sqlite3.connect = _connect
# ──────────────────────────────────────────────────────────────────────

from mcp.server import Server
from mcp.types import Tool, TextContent
from mem0 import Memory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mem0-mcp")

# ── Config ─────────────────────────────────────────────────────────────
AGENT_ID = os.getenv("MEM0_AGENT_ID", "agent-memory")
COLLECTION_NAME = os.getenv("MEM0_COLLECTION", "agent_memory")
LLM_MODEL = os.getenv("LLM_MODEL", "nvidia/nemotron-3-nano-30b-a3b:free")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", os.getenv("OPENAI_API_KEY", ""))
if not OPENROUTER_KEY:
    logger.warning("OPENROUTER_API_KEY not set — agents must export it in their shell env")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
os.environ["OPENAI_API_KEY"] = OPENROUTER_KEY

memory_config = {
    "llm": {
        "provider": "openai",
        "config": {
            "model": LLM_MODEL,
            "openai_base_url": "https://openrouter.ai/api/v1",
            "api_key": OPENROUTER_KEY,
            "temperature": 0,
            "max_tokens": 2000,
        }
    },
    "embedder": {
        "provider": "ollama",
        "config": {
            "model": "nomic-embed-text",
            "ollama_base_url": OLLAMA_URL,
        }
    },
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": COLLECTION_NAME,
            "url": QDRANT_URL,
            "embedding_model_dims": 768,
        }
    },
    "history_db_path": ":memory:",
}

memory = Memory.from_config(memory_config)
logger.info(f"Mem0 MCP server initialized (collection: {COLLECTION_NAME})")

server = Server("mem0-memory")


# ── Tools ──────────────────────────────────────────────────────────────

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="mem0_add",
            description="Add a memory entry.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Memory content"},
                    "agent_id": {"type": "string", "description": "Agent/user identifier"},
                    "category": {"type": "string", "description": "Category: architecture, convention, bugfix, preference, plan, tdd"}
                },
                "required": ["content"]
            }
        ),
        Tool(
            name="mem0_search",
            description="Search memories by semantic similarity.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "agent_id": {"type": "string", "description": "Agent identifier"},
                    "limit": {"type": "integer", "description": "Max results (default: 5)"}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="mem0_list",
            description="List all memories for an agent.",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": "Agent identifier"},
                    "limit": {"type": "integer", "description": "Max results (default: 20)"}
                }
            }
        ),
        Tool(
            name="mem0_delete",
            description="Delete a memory by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_id": {"type": "string", "description": "Memory UUID to delete"},
                    "agent_id": {"type": "string", "description": "Agent identifier"}
                },
                "required": ["memory_id"]
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    agent_id = arguments.get("agent_id", AGENT_ID) if arguments else AGENT_ID

    try:
        if name == "mem0_add":
            metadata = {"category": arguments.get("category", "general")}
            result = memory.add(arguments["content"], user_id=agent_id, metadata=metadata)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "mem0_search":
            results = memory.search(
                query=arguments["query"],
                user_id=agent_id,
                limit=arguments.get("limit", 5)
            )
            return [TextContent(type="text", text=json.dumps(results, indent=2))]

        elif name == "mem0_list":
            results = memory.get_all(
                user_id=agent_id,
                limit=arguments.get("limit", 20)
            )
            return [TextContent(type="text", text=json.dumps(results, indent=2))]

        elif name == "mem0_delete":
            result = memory.delete(arguments["memory_id"], user_id=agent_id)
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


async def main():
    from mcp.server.stdio import stdio_server
    logger.info("Starting Mem0 MCP server...")
    async with stdio_server(server) as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
        logger.info("Mem0 MCP server stopped")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
