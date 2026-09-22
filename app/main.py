from typing import Any

from fastapi import FastAPI

from app.resources.system_monitor import get_system_status


APP_VERSION = "0.1.0"


app = FastAPI(
    title="Assistant Server",
    description="Backend API for the Assistant Platform",
    version=APP_VERSION,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "assistant-server",
        "version": APP_VERSION,
    }


@app.get("/status")
def status() -> dict[str, Any]:
    return {
        "service": "assistant-server",
        "version": APP_VERSION,
        **get_system_status(),
    }