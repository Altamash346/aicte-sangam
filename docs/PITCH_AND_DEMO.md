# Pitch & demo script (5 minutes)

## 30-second problem
The same institution can be under a PGRC grievance and an RB show-cause notice at once - with nobody seeing both. Result: duplicate work,
parallel or even *contradictory* orders, delays, and no single answer to "who is handling this institution?".

## Our answer (one sentence)
A single-window dashboard that links every complaint to one institution record, shows who holds it and its full history, and raises
**"Potential Overlapping Cases - Coordination Required"** (and conflicting-action warnings) - even when the wording, language or institution name differs.

## Demo flow (use the ▶ Guided demo button; sign in as `chairman`)
1. **Dashboard (30s)** - KPIs, red overlap/conflict banner, impact card. "Every Bureau on one screen."
2. **Overlap Centre (60s)** - open a High pair: PGRC (complainant's words, maybe Hindi) vs RB (official wording). Read the plain-language reason. Unrelated matters at the same institution are *not* flagged.
3. **Conflicting actions (30s)** - "RB withdrew approval while PGRC found the institution compliant. The PS asks to prevent *conflicting* actions - we catch exactly that."
4. **Intake pre-check (60s)** - Register Complaint -> "Fill demo complaint" (Hinglish, misspelt name). Institution matched with confidence, Bureau suggested, existing cases surfaced *before* registering.
5. **Human decision (30s)** - Make RB the lead; show it recorded in both case histories. "Nothing is auto-merged; officers stay in control."
6. **Alerts + Reports (30s)** - SLA/escalation alerts, "my cases"; Bureau report -> CSV / Print to PDF.
7. **Trust (30s)** - Sign in as a PGRC officer: cannot act on RB cases, cannot see sealed ragging cases. Audit Trail (chairman): hash chain intact.

## What to say about accuracy (be precise - judges notice)
"On our synthetic benchmark the matcher made zero wrong automatic links and sent uncertain cases to an officer; the overlap engine found all planted overlaps in English, Hinglish and Hindi.
It is synthetic, so we treat it as a regression test; the next step is validating on AICTE's expert-labelled cases." Never claim a real-world accuracy percentage.

## Likely questions
- **Why not an LLM?** Deterministic, explainable, offline, no complaint data leaves AICTE; an embedding model can be added behind the same interface.
- **Wrong match?** Confidence bands: low-confidence goes to officer review; every flag shows its reason; officers can mark "not related".
- **Privacy?** Complainant contact is hashed; sensitive cases are need-to-know and view-logged; role/region scoping is server-side.
- **Integration?** Ingest API/CSV import for existing portals, SSO, PostgreSQL, HTTPS; background jobs for e-mail/SMS alerts.
- **Scale?** Indexed relational schema; overlap scoring is per-institution (small groups), so cost grows roughly linearly with cases.
- **Impact numbers?** Estimates from live counts x a stated, adjustable hours-per-duplicate assumption - not a measurement.
