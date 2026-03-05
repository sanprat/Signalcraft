from universal_agent_hooks import GeminiAgentMemory

memory = GeminiAgentMemory()

memory.post_task_hook(
    task="Fix Minervini Trend Template failing and implement Redis caching for screeners",
    result="Fixed `numpy.float32` serialization error inside `minervini_trend_template`. Added `redis` service to `docker-compose.yml`. Implemented Redis caching inside `run_screener_on_universe` Endpoint for 1 hour.",
    success=True,
    files=[
        "backend/app/services/screener.py",
        "backend/app/routers/screeners.py",
        "docker-compose.yml",
        "backend/requirements.txt"
    ],
    errors=[
        "ValueError: [TypeError(\"'numpy.float32' object is not iterable\")] from FastAPI JSON encoder."
    ]
)
print("Memory updated successfully.")
