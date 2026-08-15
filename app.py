"""
Sidekick AI — FastAPI application entry point.
"""

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Prevent oauthlib from failing on resolved alias scope changes
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = 'True'

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
from routes.linkedin import router as linkedin_router
from routes.telegram import router as telegram_router
from routes.discord import router as discord_router, discord_callback
from routes.ai import router as ai_router

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
    import traceback
    logger.info("APP_VERSION_MARKER: starting new deploy version")
    print("APP_VERSION_MARKER: starting new deploy version")
    logger.info("Starting Sidekick AI v%s …", settings.VERSION)
    try:
        # Create all database tables (legacy/fallback)
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables ready.")

        # Backfill category = "primary" for existing messages where category is None
        try:
            from database import SessionLocal
            from models.message import Message
            db = SessionLocal()
            updated_count = db.query(Message).filter(Message.category.is_(None)).update(
                {Message.category: "primary"},
                synchronize_session=False
            )
            if updated_count > 0:
                db.commit()
                logger.info("Backfilled %d messages with category='primary'.", updated_count)
            else:
                logger.info("No messages need category backfilling.")
            db.close()
        except Exception as err:
            logger.error("Failed to backfill message categories: %s", err)

        # Run Alembic migrations automatically on startup
        try:
            from alembic.config import Config
            from alembic import command
            alembic_cfg = Config("alembic.ini")
            command.upgrade(alembic_cfg, "head")
            logger.info("Alembic database migrations applied successfully on startup.")
        except Exception as exc:
            logger.error("Failed to run Alembic migrations automatically on startup: %s", exc)

        # Start background poller task
        import asyncio
        from services.poller import start_polling
        polling_task = asyncio.create_task(start_polling())

        # Start persistent Telegram client tasks
        from services.telegram_manager import telegram_manager
        asyncio.create_task(telegram_manager.start_all_clients())

        logger.info("Sidekick AI backend is ready.")
    except Exception as e:
        print("FATAL STARTUP ERROR:")
        traceback.print_exc()
        logger.fatal("FATAL STARTUP ERROR: %s", e, exc_info=True)
        raise

    yield

    # Shutdown background poller
    polling_task.cancel()
    try:
        await polling_task
    except asyncio.CancelledError:
        logger.info("Background poller task stopped.")

    # Stop persistent Telegram client connections
    for user_id in list(telegram_manager._clients.keys()):
        await telegram_manager.stop_client(user_id)
    logger.info("Persistent Telegram clients stopped.")

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
# Caching Control Middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def add_cache_control_headers(request, call_next):
    response = await call_next(request)
    path = request.url.path
    # Prevent aggressive browser caching of frontend static pages and bundles
    if (
        path.startswith("/_next")
        or path.startswith("/static")
        or path in ("/", "/privacy", "/terms")
        or path.endswith(".html")
        or path.endswith(".js")
        or path.endswith(".css")
    ):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


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
app.include_router(linkedin_router, prefix=API_PREFIX)
app.include_router(telegram_router, prefix=API_PREFIX)
app.include_router(discord_router, prefix=API_PREFIX)
app.include_router(discord_router, prefix="/api")
app.include_router(discord_router, prefix="")
app.include_router(ai_router,      prefix=API_PREFIX)

# Direct callback route registrations for Discord to prevent any router prefix translation / 404 issues
app.get("/api/discord/callback", tags=["Discord"])(discord_callback)
app.get("/api/v1/discord/callback", tags=["Discord"])(discord_callback)
app.get("/discord/callback", tags=["Discord"])(discord_callback)

# ---------------------------------------------------------------------------
# Root / Frontend UI + Health
# ---------------------------------------------------------------------------

# Mount the frontend directory to serve static assets (CSS, JS, images, etc.)
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Serve Next.js static build assets at /_next to support static frontend routes
next_dir = os.path.join("frontend", "out", "_next")
if not os.path.exists(next_dir):
    os.makedirs(next_dir, exist_ok=True)
app.mount("/_next", StaticFiles(directory=next_dir), name="next")


@app.get("/logo.png", tags=["Static"])
async def serve_logo():
    """Serve the canonical logo.png file."""
    paths = [
        os.path.join("frontend", "out", "logo.png"),
        os.path.join("frontend", "public", "logo.png"),
    ]
    for p in paths:
        if os.path.exists(p):
            return FileResponse(p)
    return HTMLResponse(status_code=404, content="Logo not found")

@app.get("/manifest.json", tags=["Static"])
async def serve_manifest():
    """Serve the manifest.json file."""
    paths = [
        os.path.join("frontend", "out", "manifest.json"),
        os.path.join("frontend", "public", "manifest.json"),
    ]
    for p in paths:
        if os.path.exists(p):
            return FileResponse(p)
    return HTMLResponse(status_code=404, content="Manifest not found")

@app.get("/favicon.ico", tags=["Static"])
async def serve_favicon():
    """Serve the favicon.ico file."""
    paths = [
        os.path.join("frontend", "out", "favicon.ico"),
        os.path.join("frontend", "public", "favicon.ico"),
        os.path.join("frontend", "src", "app", "favicon.ico"),
    ]
    for p in paths:
        if os.path.exists(p):
            return FileResponse(p)
    return HTMLResponse(status_code=404, content="Favicon not found")

@app.get("/sw.js", tags=["Static"])
async def serve_sw():
    """Serve the service worker sw.js file."""
    paths = [
        os.path.join("frontend", "out", "sw.js"),
        os.path.join("frontend", "public", "sw.js"),
    ]
    for p in paths:
        if os.path.exists(p):
            return FileResponse(p, media_type="application/javascript")
    return HTMLResponse(status_code=404, content="Service worker not found")


@app.get("/", tags=["Root"])
async def serve_frontend():
    """Serve the frontend user interface index.html file at root URL."""
    paths = [
        os.path.join("frontend", "out", "index.html"),
        os.path.join("frontend", "index.html"),
    ]
    for p in paths:
        if os.path.exists(p):
            return FileResponse(p)
    return {
        "success": True,
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "running",
        "docs": "/docs",
    }


# ---------------------------------------------------------------------------
# Legal / Static route fallback content generators
# ---------------------------------------------------------------------------

def markdown_to_html(md_path: str) -> tuple[str, str, str]:
    """Parses a simple markdown file and returns (title, effective_date, content_html)."""
    import re
    if not os.path.exists(md_path):
        return "", "", ""
        
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.splitlines()
    title = ""
    effective_date = ""
    html_parts = []
    
    in_list = False
    in_sub_list = False
    
    bold_pat = re.compile(r'\*\*(.*?)\*\*')
    code_pat = re.compile(r'`(.*?)`')
    link_pat = re.compile(r'\[(.*?)\]\((.*?)\)')

    def clean_inline(text: str) -> str:
        text = bold_pat.sub(r'<strong>\1</strong>', text)
        text = code_pat.sub(r'<code>\1</code>', text)
        text = link_pat.sub(r'<a href="\2">\1</a>', text)
        return text

    for line in lines:
        stripped = line.strip()
        
        if line.startswith("# ") and not title:
            title = line[2:].strip()
            continue
            
        if "Effective Date:" in line or "effective date" in line.lower():
            date_match = re.search(r'\*\*Effective Date:\*\*\s*(.*)', line, re.IGNORECASE)
            if date_match:
                effective_date = date_match.group(1).strip()
                continue
            
        if not stripped:
            continue
            
        if stripped == "---":
            if in_sub_list:
                html_parts.append("  </ul>")
                in_sub_list = False
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append("<hr />")
            continue
            
        if stripped.startswith("## "):
            if in_sub_list:
                html_parts.append("  </ul>")
                in_sub_list = False
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append(f"<h2>{clean_inline(stripped[3:])}</h2>")
            continue
            
        if stripped.startswith("### "):
            if in_sub_list:
                html_parts.append("  </ul>")
                in_sub_list = False
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append(f"<h3>{clean_inline(stripped[4:])}</h3>")
            continue
            
        if stripped.startswith("* ") or stripped.startswith("- "):
            indent = len(line) - len(line.lstrip())
            item_text = clean_inline(stripped[2:])
            
            if indent >= 2:
                if not in_sub_list:
                    html_parts.append("  <ul>")
                    in_sub_list = True
                html_parts.append(f"    <li>{item_text}</li>")
            else:
                if in_sub_list:
                    html_parts.append("  </ul>")
                    in_sub_list = False
                if not in_list:
                    html_parts.append("<ul>")
                    in_list = True
                html_parts.append(f"  <li>{item_text}</li>")
            continue
            
        if in_sub_list:
            html_parts.append("  </ul>")
            in_sub_list = False
        if in_list:
            html_parts.append("</ul>")
            in_list = False
            
        html_parts.append(f"<p>{clean_inline(stripped)}</p>")
        
    if in_sub_list:
        html_parts.append("  </ul>")
    if in_list:
        html_parts.append("</ul>")
        
    return title, effective_date, "\n".join(html_parts)



# ---------------------------------------------------------------------------
# Legal / Static route fallback content generators
# ---------------------------------------------------------------------------

def get_legal_page_html(title: str, effective_date: str, content_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - SidekickAI</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #09090b;
            --card-bg: #18181b;
            --border-color: #27272a;
            --text-color: #e4e4e7;
            --text-muted: #a1a1aa;
            --accent-color: #6366f1;
        }}
        body {{
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: 'Inter', sans-serif;
            margin: 0;
            padding: 0;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }}
        .header {{
            border-bottom: 1px solid var(--border-color);
            background-color: rgba(9, 9, 11, 0.7);
            backdrop-filter: blur(12px);
            position: sticky;
            top: 0;
            z-index: 50;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .logo-container {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            text-decoration: none;
            color: #fff;
            font-weight: 600;
            font-size: 1.25rem;
        }}
        .back-link {{
            color: var(--text-muted);
            text-decoration: none;
            font-size: 0.875rem;
            font-weight: 500;
            transition: color 0.2s;
            border: 1px solid var(--border-color);
            padding: 0.5rem 1rem;
            border-radius: 0.5rem;
            background-color: var(--card-bg);
        }}
        .back-link:hover {{
            color: #fff;
            border-color: #52525b;
        }}
        .container {{
            max-width: 800px;
            margin: 3rem auto;
            padding: 0 1.5rem;
            flex: 1;
        }}
        .card {{
            background-color: rgba(24, 24, 27, 0.4);
            border: 1px solid var(--border-color);
            border-radius: 0.75rem;
            padding: 2.5rem;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
            backdrop-filter: blur(8px);
        }}
        h1 {{
            font-size: 2rem;
            font-weight: 700;
            margin-top: 0;
            margin-bottom: 0.5rem;
            color: #fff;
            letter-spacing: -0.025em;
        }}
        .effective-date {{
            color: var(--text-muted);
            font-size: 0.875rem;
            margin-bottom: 2rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1rem;
        }}
        h2 {{
            font-size: 1.25rem;
            font-weight: 600;
            margin-top: 2rem;
            margin-bottom: 0.75rem;
            color: #fff;
        }}
        p {{
            line-height: 1.625;
            color: var(--text-color);
            margin-top: 0;
            margin-bottom: 1.25rem;
        }}
        ul {{
            padding-left: 1.5rem;
            margin-bottom: 1.5rem;
        }}
        li {{
            margin-bottom: 0.5rem;
            line-height: 1.625;
        }}
        .footer {{
            border-top: 1px solid var(--border-color);
            padding: 2rem;
            text-align: center;
            color: var(--text-muted);
            font-size: 0.875rem;
        }}
        .footer a {{
            color: var(--text-muted);
            text-decoration: none;
            margin: 0 0.75rem;
            transition: color 0.2s;
        }}
        .footer a:hover {{
            color: #fff;
        }}
    </style>
</head>
<body>
    <header class="header">
        <a href="/" class="logo-container">
            <img src="/logo.png" alt="SidekickAI Logo" style="width:24px; height:24px; object-fit:contain; border-radius:4px;" />
            <span>Sidekick<span style="color:#a1a1aa; font-weight:400;">AI</span></span>
        </a>
        <a href="/" class="back-link">Back to App</a>
    </header>
    <main class="container">
        <article class="card">
            <h1>{title}</h1>
            <div class="effective-date">Effective Date: {effective_date}</div>
            {content_html}
        </article>
    </main>
    <footer class="footer">
        <p>&copy; 2026 SidekickAI. All rights reserved.</p>
        <p>
            <a href="/privacy">Privacy Policy</a>
            <a href="/terms">Terms of Service</a>
        </p>
    </footer>
</body>
</html>"""


@app.get("/privacy", tags=["Static"])
async def serve_privacy():
    """Serve the Privacy Policy page."""
    # Attempt to serve static exported file from Next.js build
    paths = [
        os.path.join("frontend", "out", "privacy.html"),
        os.path.join("frontend", "out", "privacy", "index.html"),
        os.path.join("frontend", "privacy.html"),
        os.path.join("frontend", "privacy", "index.html"),
    ]
    for p in paths:
        if os.path.exists(p):
            return FileResponse(p)
            
    # Fallback dynamic rendering of PRIVACY.md
    title, effective_date, content_html = markdown_to_html("PRIVACY.md")
    if not title:
        title = "Privacy Policy"
        effective_date = "August 3, 2026"
        content_html = "<p>Privacy Policy could not be loaded from PRIVACY.md.</p>"
    return HTMLResponse(content=get_legal_page_html(title, effective_date, content_html))


@app.get("/terms", tags=["Static"])
async def serve_terms():
    """Serve the Terms of Service page."""
    # Attempt to serve static exported file from Next.js build
    paths = [
        os.path.join("frontend", "out", "terms.html"),
        os.path.join("frontend", "out", "terms", "index.html"),
        os.path.join("frontend", "terms.html"),
        os.path.join("frontend", "terms", "index.html"),
    ]
    for p in paths:
        if os.path.exists(p):
            return FileResponse(p)
            
    # Fallback dynamic rendering of TERMS.md
    title, effective_date, content_html = markdown_to_html("TERMS.md")
    if not title:
        title = "Terms of Service"
        effective_date = "August 3, 2026"
        content_html = "<p>Terms of Service could not be loaded from TERMS.md.</p>"
    return HTMLResponse(content=get_legal_page_html(title, effective_date, content_html))

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
