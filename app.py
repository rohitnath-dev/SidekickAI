"""
Sidekick AI — FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import Base, engine

# Routes
from routes.auth import router as auth_router
from routes.gmail import router as gmail_router
from routes.summary import router as summary_router
from routes.reply import router as reply_router
from routes.priority import router as priority_router
from routes.memory import router as memory_router
from routes.planner import router as planner_router
from routes.calendar import router as calendar_router
from routes.twitter import router as twitter_router
from routes.whatsapp import router as whatsapp_router
from routes.settings import router as settings_router

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Sidekick AI v%s …", settings.VERSION)

    # Create all database tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ready.")

    logger.info("Sidekick AI backend is ready.")
    yield

    # Shutdown — close the LLM async client
    from services.llm import llm
    await llm.close()
    logger.info("Sidekick AI backend shut down.")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

API_PREFIX = "/api/v1"

app.include_router(auth_router,     prefix=API_PREFIX)
app.include_router(gmail_router,    prefix=API_PREFIX)
app.include_router(summary_router,  prefix=API_PREFIX)
app.include_router(reply_router,    prefix=API_PREFIX)
app.include_router(priority_router, prefix=API_PREFIX)
app.include_router(memory_router,   prefix=API_PREFIX)
app.include_router(planner_router,  prefix=API_PREFIX)
app.include_router(calendar_router, prefix=API_PREFIX)
app.include_router(twitter_router,  prefix=API_PREFIX)
app.include_router(whatsapp_router, prefix=API_PREFIX)
app.include_router(settings_router, prefix=API_PREFIX)


# ---------------------------------------------------------------------------
# Root + Health
# ---------------------------------------------------------------------------

@app.get("/", tags=["Root"])
async def root():
    return {
        "success": True,
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "database": "connected",
    }


# ---------------------------------------------------------------------------
# Dev entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )
