from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from starlette.middleware.trustedhost import TrustedHostMiddleware

from api.auth import router as auth_router
from api.contracts import router as contracts_router
from api.webhooks import router as webhooks_router
from config import settings


# Configure application logging once at startup.
logger.remove()
logger.add(
    sink=lambda message: print(message, end=""),
    level=settings.LOG_LEVEL,
    backtrace=settings.DEBUG,
    diagnose=settings.DEBUG,
)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered multi-agent system for contract analysis",
    docs_url="/docs",
    redoc_url="/redoc",
)


# Development-friendly CORS setup. Restrict origins in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trusted hosts middleware protects against Host header attacks.
# Use explicit hostnames in production environments.
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(contracts_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")


@app.get("/")
def read_root() -> dict[str, str]:
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
    }


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
    }


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("Application started")
    logger.info("Environment: {}", settings.ENVIRONMENT)
    logger.info("API docs available at: {}", app.docs_url)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    logger.info("Application shutting down")
