"""
Main entry point for the Sidekick AI backend.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine

# Routers
from routes.gmail import router as gmail_router
from routes.summary import router as summary_router
from routes.reply import router as reply_router

# Config
from config import settings


# --------------------------------------------------
# Application Lifespan
# --------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs once when the server starts
    and once before it shuts down.
    """

    print("Starting Sidekick AI...")

    # Create database tables
    Base.metadata.create_all(bind=engine)

    print("Database connected.")
    print("Backend ready.")

    yield

    print("Shutting down Sidekick AI Backend...")


# --------------------------------------------------
# FastAPI App
# --------------------------------------------------

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    lifespan=lifespan,
)


# --------------------------------------------------
# Middleware
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# Register Routes
# --------------------------------------------------

app.include_router(
    gmail_router,
    prefix="/api/v1/gmail",
    tags=["Gmail"],
)

app.include_router(
    summary_router,
    prefix="/api/v1/summary",
    tags=["Summary"],
)

app.include_router(
    reply_router,
    prefix="/api/v1/reply",
    tags=["Reply"],
)


# --------------------------------------------------
# Root Endpoint
# --------------------------------------------------

@app.get("/", tags=["Root"])
async def root():
    return {
        "success": True,
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "running",
        "docs": "/docs",
    }


# --------------------------------------------------
# Health Check
# --------------------------------------------------

@app.get("/health", tags=["Health"])
async def health():
    return {
        "status": "healthy",
        "database": "connected",
        "service": "running",
    }
