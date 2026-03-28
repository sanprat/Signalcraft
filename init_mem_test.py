from universal_agent_hooks import GeminiAgentMemory

memory = GeminiAgentMemory()
task = "Plan architecture to remove Live Trading and Brokers, migrate to KlineChart, and setup Hybrid Strategy Builder with Telegram Webhook execution"
context = memory.pre_task_hook(task)
print("CONTEXT_LOADED:")
print(context)
