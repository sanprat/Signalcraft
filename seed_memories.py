"""
Seed experience-based memories into Mem0.

Experience > Abstract rules. Agents search for real-world problems, not textbook rules.

Usage:
  OPENROUTER_API_KEY=sk-or-v1-... MEM0_COLLECTION=myproject python3 seed_memories.py
"""
import os, time, sqlite3

# Patch sqlite3 BEFORE mem0 import
_orig = sqlite3.connect
def _patch(*a, **k):
    k.setdefault("check_same_thread", False)
    return _orig(*a, **k)
sqlite3.connect = _patch

from mem0 import Memory

openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
os.environ["OPENAI_API_KEY"] = openrouter_key

COLLECTION = os.getenv("MEM0_COLLECTION", "agent_memory")
LLM_MODEL = os.getenv("LLM_MODEL", "nvidia/nemotron-3-nano-30b-a3b:free")

config = {
    "llm": {
        "provider": "openai",
        "config": {
            "model": LLM_MODEL,
            "openai_base_url": "https://openrouter.ai/api/v1",
            "api_key": openrouter_key,
            "temperature": 0,
            "max_tokens": 2000,
        }
    },
    "embedder": {
        "provider": "ollama",
        "config": {
            "model": "nomic-embed-text",
            "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        }
    },
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": COLLECTION,
            "url": os.getenv("QDRANT_URL", "http://localhost:6333"),
            "embedding_model_dims": 768,
        }
    },
    "history_db_path": ":memory:",
}

print(f"Initializing Mem0 (collection: {COLLECTION})...")
m = Memory.from_config(config)

# ──────────────────────────────────────────────────────────────
# TDD MEMORIES — Experience + Decision + Rule Hybrid
# ──────────────────────────────────────────────────────────────
TDD_MEMORIES = [
    # Experience-driven (HIGH VALUE — matches how agents search)
    ("Previously writing implementation before tests led to unclear requirements and rework. Always start with a failing test first.", "tdd"),
    ("Fixing tests instead of implementation caused false confidence and hidden bugs. When a test fails, fix the code not the test.", "tdd"),
    ("Writing multiple failing tests at once made debugging extremely difficult. Stick to one failing test at a time.", "tdd"),
    ("Refactoring while tests were failing broke everything and wasted hours. Only refactor when all tests are green.", "tdd"),

    # Rule anchors (still useful for enforcement)
    ("TDD cycle is strictly Red → Green → Refactor. Do not skip any step.", "tdd"),
    ("Write the minimum code to make the failing test pass. No over-engineering during the green phase.", "tdd"),
    ("Test file must exist and the test must fail before any implementation file is created or modified.", "tdd"),
]

# ──────────────────────────────────────────────────────────────
# DECISION MEMORIES — Why we do things a certain way
# ──────────────────────────────────────────────────────────────
DECISIONS = [
    ("Using TDD improves agent reliability because it enforces incremental correctness and catches regressions early.", "decision"),
    ("Minimal code during green phase prevents over-engineering and reduces the surface area for bugs.", "decision"),
    ("One failing test at a time creates a clear feedback loop and makes debugging trivial.", "decision"),
]

# ──────────────────────────────────────────────────────────────
# ANTI-PATTERNS — What NOT to do (goldmine for retrieval)
# ──────────────────────────────────────────────────────────────
ANTI_PATTERNS = [
    ("Writing large chunks of code before running any tests leads to cascading failures that are painful to debug.", "anti_pattern"),
    ("Skipping the refactor step results in messy, hard-to-maintain code that degrades quickly over iterations.", "anti_pattern"),
    ("Modifying test assertions to make them pass creates false positives — tests pass but the code is still wrong.", "anti_pattern"),
]

# ──────────────────────────────────────────────────────────────
# Combine all
# ──────────────────────────────────────────────────────────────
ALL_MEMORIES = TDD_MEMORIES + DECISIONS + ANTI_PATTERNS

print(f"\n=== Seeding {len(ALL_MEMORIES)} Memories ===")
for i, (text, category) in enumerate(ALL_MEMORIES, 1):
    try:
        result = m.add(
            text,
            user_id="shared_rules",
            metadata={"type": category, "scope": "global", "source": "seed_v2"}
        )
        stored = len(result.get("results", []))
        print(f"[{i}/{len(ALL_MEMORIES)}] ✓ Stored ({stored} entries) [{category}]")
        time.sleep(1)
    except Exception as e:
        print(f"[{i}/{len(ALL_MEMORIES)}] ✗ Error: {e}")

# ──────────────────────────────────────────────────────────────
# Verification — realistic search queries agents would use
# ──────────────────────────────────────────────────────────────
print("\n=== Verification ===")
queries = [
    "test failing but code works",
    "why did test pass incorrectly",
    "writing code before tests",
    "too many failing tests",
    "when is it safe to refactor",
]
for query in queries:
    results = m.search(query, user_id="shared_rules", limit=2)
    if results.get("results"):
        print(f"\n🔍 \"{query}\" → {len(results['results'])} result(s):")
        for r in results["results"]:
            print(f"   • [{r['metadata'].get('type', '?')}] {r['memory'][:90]}")
    else:
        print(f"\n🔍 \"{query}\" → 0 results")

print(f"\n✅ Seeding complete! {len(ALL_MEMORIES)} memories stored in collection '{COLLECTION}'")
