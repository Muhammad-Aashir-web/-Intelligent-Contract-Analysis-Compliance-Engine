"""This file organizes all API routers in a single importable package entrypoint."""

from api.auth import router as auth_router
from api.contracts import router as contracts_router
from api.webhooks import router as webhooks_router

__all__ = ["auth_router", "contracts_router", "webhooks_router"]
