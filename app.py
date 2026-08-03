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

    # Start background poller task
    import asyncio
    from services.poller import start_polling
    polling_task = asyncio.create_task(start_polling())

    logger.info("Sidekick AI backend is ready.")
    yield

    # Shutdown background poller
    polling_task.cancel()
    try:
        await polling_task
    except asyncio.CancelledError:
        logger.info("Background poller task stopped.")

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
app.include_router(linkedin_router, prefix=API_PREFIX)


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
            <svg width="24" height="24" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="20" cy="20" r="18" stroke="currentColor" stroke-width="1.5" stroke-dasharray="6 3" opacity="0.4" />
                <path d="M 6.5,20 A 13.5,13.5 0 1,0 33.5,20 A 13.5,13.5 0 1,0 6.5,20" stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity="0.7" />
                <circle cx="20" cy="20" r="4.5" fill="currentColor" />
                <circle cx="31" cy="11" r="2.5" fill="currentColor" />
            </svg>
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
            
    # Fallback HTML content rendering PRIVACY.md
    privacy_content = """
    <p>At SidekickAI, accessible from <a href="https://sidekickai.onrender.com" style="color: var(--accent-color); text-decoration: none;">https://sidekickai.onrender.com</a>, one of our main priorities is the privacy of our visitors. This Privacy Policy document contains types of information that is collected and recorded by SidekickAI and how we use it.</p>

    <h2>Information We Collect</h2>
    <p>SidekickAI integrates with third-party services like Google, LinkedIn, and WhatsApp to provide AI-driven assistant features. When you authenticate via Google (Gmail) or other platforms, we only access the necessary permissions required to deliver the core functionalities of the application.</p>

    <h2>How We Use Your Information</h2>
    <p>We use the information we collect in various ways, including to:</p>
    <ul>
        <li>Provide, operate, and maintain our web application.</li>
        <li>Improve, personalize, and expand our application.</li>
        <li>Communicate with you for support and updates.</li>
    </ul>

    <h2>Data Security</h2>
    <p>We value your trust in providing us your information, thus we are striving to use commercially acceptable means of protecting it.</p>

    <h2>Contact Us</h2>
    <p>If you have any questions or suggestions about our Privacy Policy, do not hesitate to contact us at <a href="mailto:humammoin@gmail.com" style="color: var(--accent-color); text-decoration: none;">humammoin@gmail.com</a>.</p>
    """
    return HTMLResponse(content=get_legal_page_html("Privacy Policy", "August 2, 2026", privacy_content))


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
            
    # Fallback HTML content rendering TERMS.md
    terms_content = """
    <p>Welcome to SidekickAI!</p>

    <p>These terms and conditions outline the rules and regulations for the use of SidekickAI's Website, located at <a href="https://sidekickai.onrender.com" style="color: var(--accent-color); text-decoration: none;">https://sidekickai.onrender.com</a>.</p>

    <p>By accessing this website we assume you accept these terms and conditions. Do not continue to use SidekickAI if you do not agree to all of the terms and conditions stated on this page.</p>

    <h2>License</h2>
    <p>Unless otherwise stated, SidekickAI and/or its licensors own the intellectual property rights for all material on SidekickAI. All intellectual property rights are reserved.</p>

    <h2>User Responsibilities</h2>
    <p>You agree to use the application only for lawful purposes and in a way that does not infringe the rights of, restrict, or inhibit anyone else's use and enjoyment of the platform.</p>

    <h2>Limitation of Liability</h2>
    <p>In no event shall SidekickAI, nor any of its officers, directors, and employees, be held liable for anything arising out of or in any way connected with your use of this website.</p>

    <h2>Contact Us</h2>
    <p>If you have any questions about these Terms, please contact us at <a href="mailto:humammoin@gmail.com" style="color: var(--accent-color); text-decoration: none;">humammoin@gmail.com</a>.</p>
    """
    return HTMLResponse(content=get_legal_page_html("Terms of Service", "August 2, 2026", terms_content))

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
