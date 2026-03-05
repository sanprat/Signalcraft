#!/usr/bin/env python3
"""
Universal Agent Memory Hooks
Integrates memory system with any AI agent (Claude, Gemini, GPT, etc.)
"""

import os
import sys
import json
import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from init_agent_memory import get_project_integrator
except ImportError:
    print("Warning: Memory system not available")
    get_project_integrator = None


class UniversalAgentMemory:
    """Universal memory integration for any AI agent"""

    def __init__(self, agent_name: str = "agent"):
        self.agent_name = agent_name
        self.integrator = None

        if get_project_integrator:
            try:
                self.integrator = get_project_integrator()
                self.integrator.initialize_for_agent(agent_name)
                print(f"✓ Memory system initialized for {agent_name}")
            except Exception as e:
                print(f"Warning: Could not initialize memory: {e}")

    def before_task(self, task_description: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Call before starting any task

        Args:
            task_description: What the agent is about to do
            context: Additional context (model info, etc.)

        Returns:
            Dictionary with relevant memories and recommendations
        """
        if not self.integrator:
            return {}

        # Store agent info
        if context:
            self.integrator.memory.store_context(
                "agent_info",
                f"{self.agent_name}: {json.dumps(context, separators=(',', ':'))}",
                "normal"
            )

        # Create checkpoint
        checkpoint_id = self.integrator.before_task(task_description)

        # Gather relevant context
        result = {
            "checkpoint_id": checkpoint_id,
            "recent_decisions": self._get_recent_decisions(),
            "relevant_patterns": self._get_patterns_for_task(task_description),
            "known_errors": self._get_relevant_errors(task_description),
            "project_context": self._get_project_context()
        }

        return result

    def after_task(self, task_description: str, success: bool = True,
                   files_modified: Optional[List[str]] = None,
                   errors: Optional[List[Dict]] = None,
                   decisions_made: Optional[List[str]] = None,
                   patterns_learned: Optional[List[str]] = None) -> None:
        """
        Call after completing any task

        Args:
            task_description: What was done
            success: Whether the task succeeded
            files_modified: List of files that were changed
            errors: List of errors encountered
            decisions_made: Decisions made during the task
            patterns_learned: New patterns discovered
        """
        if not self.integrator:
            return

        # Store completion
        self.integrator.after_task(
            task_description,
            success,
            files_modified or [],
            errors or []
        )

        # Store decisions made
        if decisions_made:
            for decision in decisions_made:
                self.integrator.memory.store_decision(
                    decision,
                    f"Made by {self.agent_name} during: {task_description}",
                    ",".join(files_modified or []),
                    "medium"
                )

        # Store patterns learned
        if patterns_learned:
            for pattern in patterns_learned:
                self.integrator.memory.store_pattern(
                    f"{self.agent_name}_{pattern}",
                    f"Pattern learned during {task_description}",
                    f"Discovered by {self.agent_name}",
                    "learned",
                    f"{self.agent_name},auto-generated"
                )

        print(f"✓ Memory updated for {self.agent_name}: {task_description}")

    def _get_recent_decisions(self) -> List[str]:
        """Get recent decisions from memory"""
        try:
            decisions_file = Path(".agent_memory/decisions/decisions.jsonl")
            if decisions_file.exists():
                decisions = []
                with open(decisions_file) as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            decisions.append(f"- {data.get('decision', 'Unknown')}")
                return decisions[-5:]  # Last 5 decisions
        except:
            pass
        return []

    def _get_patterns_for_task(self, task_description: str) -> List[str]:
        """Get relevant patterns for the task"""
        patterns = []
        task_lower = task_description.lower()

        # Keyword-based pattern recommendations
        pattern_map = {
            "test": "Test-driven development patterns",
            "api": "REST API design patterns",
            "database": "Database access patterns",
            "error": "Error handling patterns",
            "security": "Security patterns",
            "performance": "Performance optimization patterns",
            "refactor": "Code refactoring patterns",
            "deploy": "Deployment patterns"
        }

        for keyword, pattern in pattern_map.items():
            if keyword in task_lower:
                patterns.append(pattern)

        return patterns

    def _get_relevant_errors(self, task_description: str) -> List[str]:
        """Get relevant error patterns"""
        try:
            errors_file = Path(".agent_memory/errors/errors.jsonl")
            if errors_file.exists():
                errors = []
                with open(errors_file) as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            error_type = data.get('error_type', '')
                            if any(word in task_description.lower() for word in error_type.lower().split()):
                                errors.append(f"- {error_type}: {data.get('solution', 'No solution')}")
                return errors[:3]  # Top 3 relevant errors
        except:
            pass
        return []

    def _get_project_context(self) -> str:
        """Get current project context"""
        context = []

        # Project structure
        py_files = list(Path(".").rglob("*.py"))
        context.append(f"Python files: {len(py_files)}")

        # Git status
        if Path(".git").exists():
            import subprocess
            try:
                result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    capture_output=True,
                    text=True
                )
                if result.stdout.strip():
                    changes = len(result.stdout.strip().split('\n'))
                    context.append(f"Uncommitted changes: {changes}")
            except:
                pass

        return "; ".join(context)


# Specific integrations for different agents

class GeminiAgentMemory(UniversalAgentMemory):
    """Memory integration specifically for Google Gemini"""

    def __init__(self):
        super().__init__("gemini")

    def pre_task_hook(self, task: str, model_info: Optional[Dict] = None) -> str:
        """
        Call this before Gemini starts a task

        Returns a formatted string with memory context to include in the prompt
        """
        memory_data = self.before_task(task, model_info)

        context_parts = []

        if memory_data.get("recent_decisions"):
            context_parts.append("## Recent Decisions:\n" + "\n".join(memory_data["recent_decisions"]))

        if memory_data.get("relevant_patterns"):
            context_parts.append("## Recommended Patterns:\n" + "\n".join([f"- {p}" for p in memory_data["relevant_patterns"]]))

        if memory_data.get("known_errors"):
            context_parts.append("## Relevant Error Patterns:\n" + "\n".join(memory_data["known_errors"]))

        if memory_data.get("project_context"):
            context_parts.append(f"## Project Context:\n{memory_data['project_context']}")

        return "\n\n".join(context_parts) if context_parts else ""

    def post_task_hook(self, task: str, result: Any, success: bool = True,
                       files: Optional[List[str]] = None,
                       errors: Optional[List[str]] = None) -> None:
        """
        Call this after Gemini completes a task
        """
        # Convert errors to proper format
        error_list = []
        if errors:
            error_list = [{"type": e, "solution": "Review and fix"} for e in errors]

        self.after_task(
            task,
            success,
            files,
            error_list
        )


class GPTAgentMemory(UniversalAgentMemory):
    """Memory integration for OpenAI GPT"""

    def __init__(self):
        super().__init__("gpt")


class ClaudeAgentMemory(UniversalAgentMemory):
    """Memory integration for Anthropic Claude"""

    def __init__(self):
        super().__init__("claude")


# Factory function
def create_memory_hook(agent_type: str) -> UniversalAgentMemory:
    """
    Create the appropriate memory hook for the agent type

    Args:
        agent_type: Type of agent (gemini, gpt, claude, or generic)

    Returns:
        Appropriate memory hook instance
    """
    hooks = {
        "gemini": GeminiAgentMemory,
        "gpt": GPTAgentMemory,
        "claude": ClaudeAgentMemory,
        "generic": UniversalAgentMemory
    }

    hook_class = hooks.get(agent_type.lower(), UniversalAgentMemory)
    return hook_class()


# Command line interface for testing
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python universal_agent_hooks.py <agent_type> <action> [args...]")
        print("\nActions:")
        print("  pre <task_description> - Get memory context before task")
        print("  post <task_description> <success> [files...] - Update memory after task")
        print("\nExample:")
        print("  python universal_agent_hooks.py gemini pre 'Add authentication to API'")
        print("  python universal_agent_hooks.py gemini post 'Add authentication' true auth.py main.py")
        sys.exit(1)

    agent_type = sys.argv[1]
    action = sys.argv[2]

    memory = create_memory_hook(agent_type)

    if action == "pre":
        if len(sys.argv) < 4:
            print("Error: task description required for pre action")
            sys.exit(1)
        task = " ".join(sys.argv[3:])

        if agent_type.lower() == "gemini":
            context = memory.pre_task_hook(task)
            if context:
                print("\n=== MEMORY CONTEXT ===")
                print(context)
                print("=== END CONTEXT ===\n")
        else:
            data = memory.before_task(task)
            print(f"Memory context: {json.dumps(data, indent=2)}")

    elif action == "post":
        if len(sys.argv) < 5:
            print("Error: task description and success status required")
            sys.exit(1)
        task = sys.argv[3]
        success = sys.argv[4].lower() == "true"
        files = sys.argv[5:] if len(sys.argv) > 5 else None

        memory.after_task(task, success, files)
        print(f"Memory updated for task: {task}")

    else:
        print(f"Unknown action: {action}")
        sys.exit(1)