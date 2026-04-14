#!/usr/bin/env python3
"""
Generate Mem0 MCP configs for all supported AI coding agents.

Usage:
  OPENROUTER_API_KEY=sk-or-v1-... python3 generate_configs.py

Supported agents: Claude Code, OpenCode, Qwen Code, KiloCode, Antigravity
"""
import json
import os

AGENT_ID = os.getenv("MEM0_AGENT_ID", "agent-memory")
COLLECTION = os.getenv("MEM0_COLLECTION", "agent_memory")
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MCP_SCRIPT = os.path.join(PROJECT_DIR, "mem0_mcp_server.py")

# ── MCP Server Definition ──────────────────────────────────────
MCP_SERVER = {
    "mem0": {
        "command": "python3",
        "args": [MCP_SCRIPT],
        "env": {
            "MEM0_AGENT_ID": AGENT_ID,
            "MEM0_COLLECTION": COLLECTION,
            "NOTE": "Set OPENROUTER_API_KEY in your shell env before starting the agent",
        },
    }
}


def write_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  ✅ {os.path.relpath(path, PROJECT_DIR)}")


print(f"Generating MCP configs (agent: {AGENT_ID}, collection: {COLLECTION})...\n")

# 1. Claude Code
write_json(os.path.join(PROJECT_DIR, ".mcp.json"), {"mcpServers": MCP_SERVER})

# 2. OpenCode
try:
    with open(os.path.join(PROJECT_DIR, "opencode.json")) as f:
        cfg = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    cfg = {}
cfg.setdefault("mcp", {})
cfg["mcp"]["servers"] = MCP_SERVER
write_json(os.path.join(PROJECT_DIR, "opencode.json"), cfg)

# 3. Qwen Code
write_json(os.path.join(PROJECT_DIR, ".qwen", "mcp.json"), {"mcpServers": MCP_SERVER})

# 4. KiloCode
write_json(os.path.join(PROJECT_DIR, ".kilocode", "mcp.json"), {"mcpServers": MCP_SERVER})

# 5. Antigravity
write_json(os.path.join(PROJECT_DIR, "mcp_config.json"), {"mcpServers": MCP_SERVER})

print(f"\n✅ All agent configs generated!")
print("\n📋 Agents can now call:")
print("  • mem0_add      — Store a memory")
print("  • mem0_search   — Semantic search")
print("  • mem0_list     — List all memories")
print("  • mem0_delete   — Delete a memory")
