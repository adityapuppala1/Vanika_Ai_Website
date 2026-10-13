# Vanika.AI website

Marketing site and waitlist for [vanika.ai](https://vanika.ai), the AI copilot for robotics engineers by Anvi Robotics.

- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**: system design, data model, security, design decisions
- **[docs/PLAN.md](docs/PLAN.md)**: go-live checklist, hardening and product roadmap, open decisions

## Architecture

```
 Browser ── vanika.ai (Azure Static Web Apps) ── Frontend_Website/   Vite, static HTML/CSS/JS
    │                                              ├─ /        landing page + 2 waitlist forms
    │                                              ├─ /admin   waitlist dashboard
    │                                              └─ /demo    product prototype (not indexed)
    │
    └── POST /vanika/subscribe ─┐
        GET  /vanika/admin/*  ──┤
                                ▼
          MailsBackend (Azure App Service) ── Backend_Website/   FastAPI
             ├─ /vanika        Vanika waitlist + admin API   ──► MongoDB Atlas (VanikaWaitlist)
             ├─ /anvi          Anvi Robotics / TheBotFactory forms      └─► Azure Communication
             └─ /investorDesk  Investor portal (OTP login)                  Services (email)
```

The backend is **shared**: it also serves the Anvi Robotics, TheBotFactory and InvestorDesk sites. Changes to
`main.py` or `config.py` affect all of them.

### Waitlist flow

1. A visitor submits an email on vanika.ai (hero form `source=hero`, bottom form `source=final_cta`).
2. `POST /vanika/subscribe` rate-limits by IP, checks the honeypot and access key, then validates and lowercases
   the email.
3. The sign-up is **upserted** into MongoDB, with one document per email. Repeat sign-ups increment
   `signup_count` and add the form to `sources`, so the collection count is the number of unique people.
4. For new sign-ups only, the response returns immediately and two emails go out in the background: one to the
   team and one welcome email to the subscriber. Their delivery result is saved on the document (`email_status`).
5. If MongoDB is unavailable, the sign-up is still emailed to the team, with a warning that it was not stored.

### Viewing the waitlist

Open **`https://vanika.ai/admin`** and sign in with the backend's `VANIKA_ADMIN_KEY`. The dashboard shows:

- total sign-ups, and sign-ups for today, the last 7 days and the last 30 days
- a daily chart
- a breakdown by form
- a searchable subscriber list with email delivery status

You can also export everything to CSV or remove an entry, for example after a deletion request.

## Repository layout

```
.github/workflows/
  ci.yml               backend tests (Python 3.10) + frontend build, on every push/PR
  backend-deploy.yml   deploys Backend_Website to Azure on push to main
Backend_Website/
  main.py              app, CORS + origin firewall, router registration
  config.py            settings (env vars), MongoDB + Azure Blob clients
  Vanika_Mailing/      routes.py (subscribe + admin API), waitlist.py (storage),
                       security.py (admin key, rate limits), helpers.py (email), email_templates.py
  Anvi_Mailing/, Email_Templates/, InvestorDesk/   other sites served by the same backend
  tests/               pytest suite (in-memory MongoDB, stubbed email)
Frontend_Website/
  index.html, admin.html, demo.html
  src/main.js          landing page behaviour
  src/admin.js         dashboard
  src/lib/api.js       backend client (shared)
  src/styles/          tokens.css (shared design tokens), site.css, admin.css
  public/              icons, logos, robots.txt, sitemap, Azure SWA config
docs/                  ARCHITECTURE.md, PLAN.md
docker-compose.dev.yml local MongoDB
```

## Local development

**Database** (Docker):

```bash
docker compose -f Frontend_Website/
  index.html, admin.html, demo.html up -d   # MongoDB on localhost:27017
```

**Backend** (Python 3.10+):

```bash
cd Backend_Website
cp .env.example .env              # MONGODB_URI=mongodb://localhost:27017, VANIKA_ADMIN_KEY=…
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn main:app --reload --port 8000
python -m pytest                   # tests need no MongoDB or ACS
```

Without ACS credentials, sign-ups are still stored, and the dashboard shows the emails as failed (✕).

**Frontend** (Node 20.19+):

```bash
cd Frontend_Website
cp .env.example .env              # VITE_API_BASE_URL=http://127.0.0.1:8000
npm install
npm run dev                       # http://localhost:5173, admin at /admin
```

## Configuration

| Variable | Where | Purpose |
|---|---|---|
| `MONGODB_URI` | backend | **Required to store sign-ups.** Without it, sign-ups are only emailed. |
| `VANIKA_ADMIN_KEY` | backend | Private key for `/admin`. The admin API is disabled when it is empty. |
| `CORS_ORIGINS` | backend | Allowed origins, comma-separated. Must include `https://vanika.ai` and `https://www.vanika.ai`. |
| `AZURE_COMMUNICATION_CONNECTION_STRING`, `EMAIL_PRIMARY_VANIKA` | backend | Email sending (ACS) |
| `VANIKA_ROUTES_KEY` / `VITE_MAIL_ACCESS_KEY` | backend / frontend | Must match. It is public in the JS bundle, so it only filters casual bots. |
| `VITE_API_BASE_URL` | frontend build | Backend base URL. The older `VITE_MAIL_BACKEND_URL` still works. |

The full lists are in `Backend_Website/.env.example` and `Frontend_Website/.env.example`.

## API

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/vanika/subscribe` | access key | Form fields: `clientemail`, `source`, `accesskey`, optional `utm_*`, `referrer` |
| `GET` | `/vanika/admin/stats` | `X-Admin-Key` | Totals, daily series, by-source counts |
| `GET` | `/vanika/admin/subscribers?search=&limit=&offset=` | `X-Admin-Key` | Paginated list |
| `GET` | `/vanika/admin/subscribers/export.csv` | `X-Admin-Key` | CSV export |
| `DELETE` | `/vanika/admin/subscribers/{email}` | `X-Admin-Key` | Remove a subscriber |
