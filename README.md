# AICTE Samvad - Integrated Institution Complaint Monitoring Dashboard
**SIH PS 26264 · AICTE · Regulation Bureau · Smart Automation**

One screen showing every institution-related complaint across RB, PGRC, Approval Bureau, Anti-Ragging Cell and Regional Offices -
who holds each case, its full history, and a warning *before* two Bureaus act on the same institution in parallel or in conflict.
All data is synthetic.

## Run (2 minutes)
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload      # open http://127.0.0.1:8000   (API docs: /docs)
python -m pytest -q                          # 19 tests
```
Windows tip: use `python -m uvicorn` / `python -m pytest` if the commands are not on PATH. Delete `backend/aicte.db` to reseed.

## 🚀 Cloud Deployment

### Option A: Render (Free Web Service)
1. Fork or push to GitHub (`Altamash346/aicte-sangam`).
2. Go to [dashboard.render.com](https://dashboard.render.com/) -> **New** -> **Web Service**.
3. Select your GitHub repository.
4. Render automatically detects `render.yaml` (or choose Python 3 runtime):
   - **Build Command**: `pip install -r backend/requirements.txt`
   - **Start Command**: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add Environment Variable:
   - `COOKIE_SECURE`: `true`
6. Click **Deploy Web Service**.

### Option B: Railway / Fly.io / Koyeb
- Simply import the GitHub repo. Railway / Fly will detect the `Dockerfile` and `railway.json` / `Procfile` and deploy automatically with zero extra configuration.

### Option C: Docker (Local / VPS)
```bash
docker compose up --build
```
Open `http://localhost:8000`.

---

**Demo logins** (password `Aicte@2026`): `chairman` (Competent Authority) · `rb.head` · `pgrc.head` · `rb.officer1` · `pgrc.officer1` · `arc.head` · `ro.western` (Regional).
Click **▶ Guided demo** in the top bar for an 8-step walkthrough. Pitch script: `docs/PITCH_AND_DEMO.md`.
**Citizen Grievance Tracking**: Open `http://127.0.0.1:8000/#/track` to track grievance status without login.

## PS requirement -> where it lives
| PS requirement | Implementation |
|---|---|
| Centralised institution profile, consolidated history | Institutions page: AICTE ID, address, region, aliases, "case family" lanes per Bureau |
| Case tracking (ID, receipt date, category, status, Bureau, officer, last/next action, expected disposal) | Cases + Case page; SLA due date per category; auto-assignment to least-loaded officer |
| Cross-Bureau overlap detection, alert, linking | `engine/overlap.py`, Overlap Centre, coordination decisions written into both case histories |
| Real-time dashboard (total, pending, under process, disposed, transferred, beyond timeline, institution-wise, Bureau workload) | Dashboard |
| Workflow & action history, transfer/escalation trail | Case page timeline; state machine (update/accept/transfer/escalate/dispose/reopen) |
| Supporting documents & attachments | Document uploads on case actions (`POST /api/cases/{id}/documents`), download endpoint, timeline viewer |
| Search & filters (name, AICTE ID, case ID, Bureau, region, category, status, dates) | Cases page + Ctrl+K palette |
| Alerts (overlap, reminders, escalation, SLA) | Alerts page, "my cases" filter, dashboard banner |
| Reports (Bureau, region, institution, ageing, disposal rate, overlaps, monthly/quarterly) | Reports page; CSV export; Print / Save as PDF |
| Bulk CSV ingestion | Bulk Ingestion wizard (`#/import`) with template download, fuzzy institution matching & overlap preview |
| Citizen grievance tracking | Public tracking portal (`#/track`) with progress stepper, SLA timeline & PII protection |
| Innovation: match cases even when wording/references differ | Fuzzy institution matcher + cross-lingual (English/Hinglish/Hindi) concept matching + **conflicting-action detection** |

## Architecture
FastAPI + SQLAlchemy (SQLite default, PostgreSQL-ready) · no-build web app served by the backend (`frontend/`) · deterministic, explainable engine (`backend/app/engine/`).
`matching.py` institution resolution · `concepts.py` cross-lingual subject extraction · `overlap.py` two-tier overlap score · `conflicts.py` contradictory-action rules.

## Security & governance
Argon2 password hashing · httpOnly SameSite session cookie · login throttling · **server-side** role and region scoping (client never decides) ·
sealed sensitive cases (need-to-know, every view logged) · complainant contact stored only as a salted hash · hash-chained tamper-evident audit log ·
security headers · input validation · all rendered text HTML-escaped. The engine only advises: **humans decide, nothing is auto-merged**.

## Honest limits
- Synthetic data for demo and validation purposes.
- Hindi/Hinglish understanding is a lexicon for 7 complaint themes; real deployment needs a larger lexicon or an embedding model (plug-in point `engine/concepts.py`).
- SLA days are illustrative and configurable (`domain.py`). Impact figures are estimates with a stated, adjustable assumption.
- No live integration with AICTE systems yet (production path: ingest API / CSV import, SSO, PostgreSQL, HTTPS, background alert jobs/e-mail/SMS).
