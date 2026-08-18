# Sidekick AI — Backend

An AI-powered executive assistant backend that helps users manage communications across Gmail, Calendar, WhatsApp, and X (Twitter).

## Tech Stack

- **Python 3.11** / **FastAPI** with async/await throughout
- **SQLAlchemy** (SQLite for dev, PostgreSQL-ready)
- **OpenRouter** LLM API (OpenAI-compatible)
- **Google OAuth 2.0** (Gmail, Calendar, Contacts)
- **Meta WhatsApp Cloud API**
- **Twitter API v2**
- **JWT** authentication (python-jose)

## Running the backend

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Or simply use the **Run** button — the workflow is pre-configured.

## Environment variables required

Copy the template from `.env` and set real values in Replit Secrets:

| Variable | Description |
|---|---|
| `SECRET_KEY` | Random hex string for JWT signing |
| `OPENROUTER_API_KEY` | OpenRouter API key |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | OAuth redirect URI (must match Google Console) |

Optional (enable specific integrations):

| Variable | Description |
|---|---|
| `TWITTER_BEARER_TOKEN` | Twitter API v2 bearer token (read) |
| `TWITTER_API_KEY` / `TWITTER_API_SECRET` | Twitter OAuth 1.0a keys |
| `TWITTER_ACCESS_TOKEN` / `TWITTER_ACCESS_SECRET` | Twitter OAuth 1.0a access tokens |
| `WHATSAPP_API_TOKEN` | Meta WhatsApp Cloud API token |
| `WHATSAPP_PHONE_NUMBER_ID` | WhatsApp phone number ID |
| `WHATSAPP_VERIFY_TOKEN` | Webhook verification token |

## API structure

All endpoints are under `/api/v1/`. Interactive docs: `/docs`

| Prefix | Description |
|---|---|
| `/auth` | Register, login, profile |
| `/gmail` | OAuth, sync, read messages |
| `/summary` | AI email summaries |
| `/reply` | AI reply generation |
| `/priority` | Message priority analysis |
| `/memory` | Long-term memory extraction |
| `/planner` | Daily briefing |
| `/calendar` | Google Calendar |
| `/twitter` | Twitter/X integration |
| `/whatsapp` | WhatsApp integration |
| `/settings` | User preferences, connected services |

## MVP User Flow

1. `POST /api/v1/auth/register` — create account
2. `POST /api/v1/auth/login` — get JWT token
3. `GET /api/v1/gmail/authorize` — get Google OAuth URL
4. Redirect user to URL → Google redirects to `/api/v1/gmail/callback?code=...`
5. `POST /api/v1/gmail/sync` — pull emails into database
6. `GET /api/v1/gmail/messages` — list stored messages
7. `POST /api/v1/summary/message/{id}` — summarise a message
8. `POST /api/v1/reply/message/{id}` — generate a reply
9. `POST /api/v1/priority/message/{id}` — score priority
10. `GET /api/v1/planner/briefing` — daily executive briefing

## Architecture

```
app.py                  FastAPI entry point
config.py               Settings (pydantic-settings, loaded from env)
database.py             SQLAlchemy engine + session factory
dependencies.py         FastAPI dependency functions (auth)

models/                 SQLAlchemy models
  user.py               User accounts
  message.py            Unified messages (all platforms)
  token.py              OAuth token storage (per user/provider)
  memory_item.py        Long-term memory facts

services/
  llm.py                Async OpenRouter LLM client (singleton)
  auth.py               JWT + password hashing
  oauth.py              Google OAuth 2.0 flow

agents/                 AI agents (all async, use LLM)
  base_agent.py         Shared LLM call, JSON parsing, retry
  gmail_agent.py        Gmail API + message sync
  summary_agent.py      Email summarisation
  priority_agent.py     Message priority scoring
  reply_agent.py        Draft reply generation
  memory_agent.py       Long-term fact extraction
  planner_agent.py      Daily briefing orchestration
  calendar_agent.py     Google Calendar integration
  twitter_agent.py      Twitter/X API
  whatsapp_agent.py     WhatsApp Cloud API

utils/prompts/          Centralised prompt package
  base.py               Shared rules, injection helpers
  system.py             Identity + operational boundaries
  summary.py, priority.py, reply.py, memory.py, planner.py
  gmail.py, calendar.py, contacts.py, whatsapp.py, twitter.py
  notification.py, personality.py

repositories/           Data access objects
  user_repo.py, message_repo.py, token_repo.py, memory_repo.py

routes/                 Thin FastAPI route handlers
  auth.py, gmail.py, summary.py, reply.py, priority.py
  memory.py, planner.py, calendar.py, twitter.py, whatsapp.py
  settings.py
```

## User preferences

- Keep routes thin — business logic belongs in agents/services
- All LLM calls are async (`await self.llm.generate(...)`)
- No `time.sleep()` anywhere — use `asyncio.sleep()`
- No secrets in code — always read from `settings.*`
- Prompts live in `utils/prompts/` — never hardcoded in agents

## Platform & API Limitations

Ensure all feature work and integrations adhere to the following hard API constraints:

### WhatsApp Integration (Meta Cloud API)
- **Business Only**: The integration utilizes the official Meta WhatsApp Business Platform (Embedded Signup flow). It **only** supports registered WhatsApp Business Accounts (WABA) with dedicated business numbers.
- **No Personal Accounts**: Personal WhatsApp numbers and accounts are not supported by Meta's API and cannot be synced or read.
- **Message Types**: Supports template messages and customer session messages initiated by customers.

