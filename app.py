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
from routes.discord import router as discord_router

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
app.include_router(telegram_router, prefix=API_PREFIX)
app.include_router(discord_router, prefix=API_PREFIX)


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
    <p>SidekickAI ("we," "our," or "us") is committed to protecting your privacy. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use our web application located at <a href="https://sidekickai.onrender.com" style="color: var(--accent-color); text-decoration: none;">https://sidekickai.onrender.com</a> (the "Service").</p>
    <p>By accessing or using our Service, you agree to the collection and use of information in accordance with this Privacy Policy. If you do not agree with any terms of this policy, please do not use the Service.</p>

    <h2>1. Information Collection</h2>
    <p>We collect several types of information to provide and improve our Service:</p>
    
    <h3>A. Information You Provide Directly</h3>
    <ul>
        <li><strong>Account Information:</strong> When you register for an account, we collect your full name, email address, password (stored securely using industry-standard hashing algorithms), and user preferences.</li>
        <li><strong>Communications:</strong> If you contact us directly, we may collect your email address, message contents, and any attachments you send.</li>
    </ul>

    <h3>B. Third-Party Integrations & OAuth Authorized Data</h3>
    <p>To deliver our AI assistant functionalities, SidekickAI connects with external platforms via OAuth protocol. We access only the permissions you explicitly grant during authentication:</p>
    <ul>
        <li><strong>Google Workspace APIs (Gmail & Calendar):</strong>
            <ul>
                <li><em>Gmail Scopes:</em> We access Gmail messages (read, modify, send, and compose permissions) to pull email history, synthesize summaries, detect priority threads, and generate draft responses.</li>
                <li><em>Google Calendar Scopes:</em> We access calendar events (read and write permissions) to retrieve your schedule timeline, update calendar entries, and compile your daily executive briefing.</li>
                <li><em>OAuth Tokens:</em> We receive and securely store encrypted Google refresh and access tokens to synchronize your data in the background.</li>
            </ul>
        </li>
        <li><strong>LinkedIn API:</strong>
            <ul>
                <li><em>Scopes Used:</em> We request profile information access and post-sharing scopes (<code>w_member_social</code>).</li>
                <li><em>Access Limitations:</em> The API only allows us to synchronize your profile metadata and share auto-generated professional posts. We do not (and cannot) read LinkedIn messages, direct chats, or private inbox content.</li>
            </ul>
        </li>
        <li><strong>WhatsApp Cloud API:</strong>
            <ul>
                <li><em>Embedded Signup flow:</em> Integrates strictly with Meta's official WhatsApp Business Platform. We access your registered WhatsApp Business Account (WABA) ID, connected phone numbers, and customer chats.</li>
                <li><em>Access Limitations:</em> This integration requires a dedicated business number. It <strong>cannot</strong> connect personal WhatsApp profiles, read personal chats, or sync standard private numbers.</li>
            </ul>
        </li>
    </ul>

    <h2>2. How We Use Your Information</h2>
    <p>We use the collected information for various purposes, including to:</p>
    <ul>
        <li>Operate the Service: Sync email lists, calendar schedules, WhatsApp customer chats, and LinkedIn profiles.</li>
        <li>Generate AI Assist Capabilities: Analyze email headers and body texts using LLMs to prioritize threads, draft proposed reply templates, and build your Daily Briefing.</li>
        <li>Improve & Personalize: Track application performance, resolve configuration bugs, and enhance user experience layouts.</li>
        <li>Security & Authentication: Verify user accounts, secure API sessions, and maintain OAuth credential token rotations.</li>
    </ul>

    <h2>3. Data Sharing & Disclosure</h2>
    <p>We do not sell, trade, or rent your personal information to third parties. We may disclose data under the following circumstances:</p>
    <ul>
        <li><strong>With Service Providers:</strong> We share content with verified sub-processors (such as LLM endpoint providers like OpenRouter) solely to process your prompts and draft summaries. These providers are bound by strict confidentiality obligations and do not use your data to train their public models.</li>
        <li><strong>Legal Requirements:</strong> If required by law, subpoena, or government regulation, we may disclose information to comply with valid legal processes.</li>
        <li><strong>Business Transfers:</strong> If SidekickAI undergoes a merger, acquisition, or asset sale, your personal information may be transferred. We will notify you before your data becomes subject to a different policy.</li>
    </ul>

    <h2>4. Data Security</h2>
    <p>We implement robust administrative, technical, and physical security measures to safeguard your credentials and data:</p>
    <ul>
        <li><strong>Encryption:</strong> All OAuth credentials (tokens) are stored in our database using strong AES-256 encryption. All network communications use secure HTTPS/TLS transport protocols.</li>
        <li><strong>Access Control:</strong> System database sessions are restricted to authenticated service layers. Database engines are isolated from direct external internet access.</li>
        <li><strong>No Cache Retention for LLMs:</strong> When we send email or chat content to LLM endpoints for synthesis, the data is passed securely and is not cached or used for training.</li>
    </ul>

    <h2>5. User Rights</h2>
    <p>Depending on your jurisdiction (such as under GDPR or CCPA), you may have the following rights regarding your data:</p>
    <ul>
        <li><strong>Access & Sync:</strong> You can view all linked data and integrations directly on the dashboard.</li>
        <li><strong>Data Rectification:</strong> You can modify your profile details and connection settings at any time in the Settings portal.</li>
        <li><strong>Data Erasure:</strong> You can delete your account or disconnect specific integrations. Disconnecting a service instantly deletes the corresponding OAuth credentials, synced messages, and cached indexes from our database.</li>
        <li><strong>Contact:</strong> To request complete account erasure or export your details, email us at <a href="mailto:humammoin09@gmail.com" style="color: var(--accent-color); text-decoration: none;">humammoin09@gmail.com</a>.</li>
    </ul>

    <h2>6. Cookies & Tracking Technologies</h2>
    <p>We use basic HTTP cookies and local storage tokens to manage user sessions and login authentication states:</p>
    <ul>
        <li><strong>Auth Cookies:</strong> Secure JWT cookie tokens are stored in your browser to maintain your session state.</li>
        <li><strong>Preferences Storage:</strong> Local storage is used to save theme states and interface layouts.</li>
        <li><strong>No Third-Party Ad Trackers:</strong> We do not host third-party advertisement trackers, analytics beacons, or retargeting scripts.</li>
    </ul>

    <h2>7. Changes to This Privacy Policy</h2>
    <p>We may update our Privacy Policy from time to time. We will notify you of any changes by posting the new Privacy Policy on this page and updating the "Effective Date" at the top.</p>

    <h2>8. Contact Us</h2>
    <p>If you have any questions or suggestions about our Privacy Policy, please contact us at <a href="mailto:humammoin09@gmail.com" style="color: var(--accent-color); text-decoration: none;">humammoin09@gmail.com</a>.</p>
    """
    return HTMLResponse(content=get_legal_page_html("Privacy Policy", "August 3, 2026", privacy_content))


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
    <p>These Terms of Service ("Terms") govern your access to and use of the SidekickAI website and web application located at <a href="https://sidekickai.onrender.com" style="color: var(--accent-color); text-decoration: none;">https://sidekickai.onrender.com</a> (the "Service" or "Platform").</p>
    <p>By accessing or using the Service, you agree to be bound by these Terms. If you disagree with any part of the terms, you may not access or use the Service.</p>

    <h2>1. Description of Service</h2>
    <p>SidekickAI is an AI-powered executive assistant platform designed to assist users in prioritizing communications, drafting replies, and coordinating schedules across connected systems (including Gmail, Google Calendar, WhatsApp Business, and LinkedIn).</p>

    <h2>2. Account Registration & Security</h2>
    <p>To use the Service, you must create a user profile. You agree to:</p>
    <ul>
        <li>Provide accurate, current, and complete registration information.</li>
        <li>Maintain the confidentiality of your password and account credentials.</li>
        <li>Accept responsibility for all actions that occur under your account session.</li>
        <li>Immediately notify us of any unauthorized use or security breaches by contacting <a href="mailto:humammoin09@gmail.com" style="color: var(--accent-color); text-decoration: none;">humammoin09@gmail.com</a>.</li>
    </ul>

    <h2>3. Third-Party Integrations & Scope Boundaries</h2>
    <p>SidekickAI utilizes API access to sync and write data on your behalf. By authorizing integrations, you acknowledge their specific functional scopes:</p>
    <ul>
        <li><strong>Google OAuth:</strong> SidekickAI is granted read/write permissions for Gmail messages and Calendar schedules to generate briefs, categorize priorities, and draft or send email replies.</li>
        <li><strong>Meta WhatsApp Cloud API:</strong> Serves only registered business accounts (WABA). Connection requires a business phone number; personal accounts cannot be linked.</li>
        <li><strong>LinkedIn Profile Sync:</strong> Restricted solely to profile metadata sync and post sharing (<code>w_member_social</code>). The Service cannot read or sync LinkedIn private DMs.</li>
    </ul>
    <p>We are not liable for any service interruptions, API deprecations, or policy changes implemented by Google, Meta, LinkedIn, or other third-party provider platforms.</p>

    <h2>4. User Responsibilities & Acceptable Use</h2>
    <p>You agree that you will not use the Service to:</p>
    <ul>
        <li>Violate any applicable local, state, national, or international laws.</li>
        <li>Distribute unsolicited promotional materials, spam, or bulk marketing messages.</li>
        <li>Inject malicious code, trojans, worms, or attempt unauthorized entry into the database.</li>
        <li>Impersonate any entity or forge email/message headers.</li>
        <li>Interfere with or disrupt the servers or networks connected to the Service.</li>
    </ul>

    <h2>5. Intellectual Property Rights</h2>
    <p>Unless otherwise stated, SidekickAI and/or its licensors own all intellectual property rights for the design, code, graphics, branding, and workflows on the Platform. All rights are reserved. You are granted a limited, non-exclusive, non-transferable license to access the interface for personal or standard business assistant operations.</p>

    <h2>6. Disclaimer of Warranties</h2>
    <p>The Service is provided on an "AS IS" and "AS AVAILABLE" basis. SidekickAI makes no representations or warranties of any kind, express or implied, as to the operation of the Service, the accuracy of AI-generated email/chat drafts, or the completeness of the briefings.</p>
    <p>We do not warrant that the Service will function uninterrupted, secure, or available at any specific time or location; that any errors or bugs in the software will be corrected immediately; or that the AI-generated drafts are free of errors. <strong>Users must review all draft replies before approving and sending.</strong></p>

    <h2>7. Limitation of Liability</h2>
    <p>To the maximum extent permitted by law, in no event shall SidekickAI, nor its directors, employees, partners, agents, or suppliers, be liable for any indirect, incidental, special, consequential, or punitive damages—including loss of profits, data, goodwill, or other intangible losses—resulting from your access to or use of (or inability to use) the Service; any conduct or content of any third party on the Service; or unauthorized access, use, or alteration of your transmissions or database content.</p>

    <h2>8. Suspension & Termination</h2>
    <p>We reserve the right to suspend or terminate your account and restrict access to the Service at our sole discretion, without prior notice or liability, for any reason, including if you breach these Terms. Upon termination, your right to use the Service will cease immediately, and all linked OAuth connections and data will be erased.</p>

    <h2>9. Governing Law</h2>
    <p>These Terms shall be governed and construed in accordance with the laws of the jurisdiction in which SidekickAI operates, without regard to its conflict of law provisions.</p>

    <h2>10. Modifications to Terms</h2>
    <p>We reserve the right to modify or replace these Terms at any time. If a revision is material, we will provide at least 15 days' notice before the new terms take effect. By continuing to access or use the Service after those revisions become effective, you agree to be bound by the updated terms.</p>

    <h2>11. Contact Us</h2>
    <p>If you have any questions about these Terms, please contact us at <a href="mailto:humammoin09@gmail.com" style="color: var(--accent-color); text-decoration: none;">humammoin09@gmail.com</a>.</p>
    """
    return HTMLResponse(content=get_legal_page_html("Terms of Service", "August 3, 2026", terms_content))

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
