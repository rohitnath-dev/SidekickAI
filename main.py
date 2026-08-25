"""
Sidekick AI — FastAPI main entrypoint alias.

Re-exports `app` from `app.py` to support servers or runners expecting `main:app`.
"""

from app import app

if __name__ == "__main__":
    import uvicorn
    from config import settings

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )

