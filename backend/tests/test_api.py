import io
import os
os.environ["DATABASE_URL"] = "sqlite:///./test_aicte.db"
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from app.db import engine, SessionLocal


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c
    engine.dispose()
    if os.path.exists("test_aicte.db"):
        os.remove("test_aicte.db")


def login(client, user, pw="Aicte@2026"):
    c = TestClient(app); r = c.post("/api/auth/login", json={"username": user, "password": pw}); return c, r


def test_auth_required_and_bad_login(client):
    assert client.get("/api/cases").status_code == 401
    assert login(client, "rb.head", "wrong")[1].status_code == 401


def test_login_throttle(client):
    codes = [login(client, "ms", "bad")[1].status_code for _ in range(7)]
    assert codes[-1] == 429


def test_rbac_act_only_on_own_bureau(client):
    c, r = login(client, "rb.officer1"); assert r.status_code == 200
    pg = c.get("/api/cases", params={"bureau": "PGRC", "size": 5}).json()["items"][0]
    assert c.get(f"/api/cases/{pg['id']}").json()["can_act"] is False
    assert c.post(f"/api/cases/{pg['id']}/actions", json={"action": "update", "remarks": "x"}).status_code == 403


def test_sealed_cases_need_to_know(client):
    pg, _ = login(client, "pgrc.head"); arc, _ = login(client, "arc.head"); adm, _ = login(client, "chairman")
    assert pg.get("/api/cases", params={"category": "ragging"}).json()["total"] == 0
    n = arc.get("/api/cases", params={"category": "ragging"}).json()["total"]
    assert n > 0 and adm.get("/api/cases", params={"category": "ragging"}).json()["total"] == n


def test_regional_scope(client):
    c, _ = login(client, "ro.western")
    items = c.get("/api/cases", params={"size": 200}).json()["items"]
    assert items and all(i["institution"]["region"] == "Western" for i in items)


def test_workflow_transfer_accept_dispose(client):
    c, _ = login(client, "rb.head")
    case = c.get("/api/cases", params={"bureau": "RB", "status": "Pending", "size": 1}).json()["items"][0]
    r = c.post(f"/api/cases/{case['id']}/actions", json={"action": "transfer", "to_bureau": "PGRC", "remarks": "Belongs to PGRC"})
    assert r.json()["bureau"] == "PGRC" and r.json()["status"] == "Transferred"
    p, _ = login(client, "pgrc.officer1")
    assert p.post(f"/api/cases/{case['id']}/actions", json={"action": "accept"}).json()["status"] == "Under Process"
    assert p.post(f"/api/cases/{case['id']}/actions", json={"action": "dispose", "remarks": "done"}).json()["status"] == "Disposed"
    assert p.post(f"/api/cases/{case['id']}/actions", json={"action": "update"}).status_code == 409


def test_create_case_and_dashboard(client):
    c, _ = login(client, "pgrc.officer1"); inst = c.get("/api/institutions").json()[0]
    r = c.post("/api/cases", json={"subject": "Fee refund pending", "description": "Refund not received after withdrawal.",
                                   "category": "fee_refund", "institution_id": inst["id"]})
    assert r.status_code == 201 and r.json()["bureau"] == "PGRC" and r.json()["officer"]
    d = c.get("/api/dashboard").json(); assert d["total"] > 100 and "bureau_workload" in d


def test_audit_chain_detects_tampering(client):
    adm, _ = login(client, "chairman")
    assert adm.get("/api/audit/verify").json()["valid"] is True
    with SessionLocal() as db:
        db.execute(text("update audit_log set detail='tampered' where id=2")); db.commit()
    assert adm.get("/api/audit/verify").json()["valid"] is False
    assert login(client, "rb.head")[0].get("/api/audit").status_code == 403


# ---------------- Phase 2: engine ----------------
import json
from app.engine import concepts as K
from app.engine.evaluate import run as evaluate_run

TRUTH = lambda: json.load(open("data/ground_truth.json"))


def test_cross_language_similarity():
    en = K.concepts("The college refuses to refund Rs 12000 after I withdrew admission.")
    hi = K.concepts("प्रवेश रद्द करने के बाद भी संस्थान ₹12000 शुल्क वापस नहीं कर रहा है।")
    hing = K.concepts("Admission cancel karne ke baad bhi college Rs 12000 fee wapas nahi kar raha hai.")
    rag = K.concepts("Senior students are harassing first-year students in the hostel.")
    assert K.cosine(en, hi) > 0.4 and K.cosine(en, hing) > 0.4 and K.cosine(en, rag) == 0


def test_matcher_never_wrong_auto_link(client):
    with SessionLocal() as db:
        m = evaluate_run(db)["institution_matcher"]
    assert m["auto_wrong"] == 0 and m["auto_link_rate"] > 0.5 and m["review"] == m["review_contains_truth"]


def test_overlap_and_conflict_recall(client):
    with SessionLocal() as db:
        r = evaluate_run(db)
    at_op = next(x for x in r["overlap_threshold_sweep"] if x["threshold"] == r["operating_threshold"])
    assert at_op["recall"] >= 0.9
    assert r["conflicts"]["found_planted"] == r["conflicts"]["planted"]
    assert all(v["found"] == v["total"] for v in r["planted_overlap_recall_by_language"].values())


def test_overlaps_endpoint_and_scoping(client):
    adm, _ = login(client, "chairman"); g = adm.get("/api/overlaps", params={"min_severity": "Medium"}).json()
    assert len(g) >= 10 and g[0]["message"].startswith("Potential Overlapping") and g[0]["pairs"][0]["explanation"]
    assert len(adm.get("/api/conflicts").json()) >= 4
    assert login(client, "rb.head")[0].get("/api/evaluation").status_code == 200
    assert login(client, "rb.officer1")[0].get("/api/evaluation").status_code == 403


def test_intake_analyze_hinglish_flags_overlap(client):
    adm, _ = login(client, "chairman"); t = TRUTH()["planted_overlaps"]
    p = next(x for x in t if x["category"] == "fee_refund")
    inst = next(i for i in adm.get("/api/institutions").json() if i["aicte_id"] == p["institution"])
    r = adm.post("/api/intake/analyze", json={"institution_ref": inst["name"], "description": "Admission cancel karne ke baad bhi college Rs 35000 fee wapas nahi kar raha hai."}).json()
    assert r["suggested_category"] == "fee_refund" and r["suggested_bureau"] == "PGRC"
    assert r["institution"]["band"] == "auto" and r["banner"] and r["similar_cases"]


def test_review_designate_lead_writes_both_histories(client):
    rbh, _ = login(client, "rb.head"); adm, _ = login(client, "chairman")
    p = next(x for x in adm.get("/api/overlaps", params={"min_severity": "Medium"}).json() if len(x["bureaus"]) == 2)["pairs"][0]
    ok = rbh.post("/api/overlaps/review", json={"case_a": p["id_a"], "case_b": p["id_b"], "decision": "designate_lead", "lead_bureau": p["bureau_a"], "note": "RB leads"})
    assert ok.status_code == 200
    bad = rbh.post("/api/overlaps/review", json={"case_a": p["id_a"], "case_b": p["id_b"], "decision": "designate_lead", "lead_bureau": "AB"})
    assert bad.status_code == 422
    for cid in (p["id_a"], p["id_b"]):
        assert any(h["action"] == "coordination" for h in adm.get(f"/api/cases/{cid}").json()["history"])
    rbh.post("/api/overlaps/review", json={"case_a": p["id_a"], "case_b": p["id_b"], "decision": "not_related"})
    again = adm.get("/api/overlaps", params={"min_severity": "Medium"}).json()
    assert all(not (q["id_a"] == p["id_a"] and q["id_b"] == p["id_b"]) for g in again for q in g["pairs"])


# ---------------- Phase 4: alerts, reports, impact ----------------
def test_alerts_reports_impact(client):
    adm, _ = login(client, "chairman"); a = adm.get("/api/alerts").json()
    types = {x["type"] for x in a["items"]}
    assert {"Overlap", "Conflicting actions"} <= types and a["counts"]["high"] > 0
    assert all(x["bureau"] == "RB" or "RB" in x["bureau"] for x in login(client, "rb.officer1")[0].get("/api/alerts", params={"mine": True}).json()["items"])
    for kind in ("bureau", "region", "institution", "category", "ageing", "monthly", "quarterly", "overlaps", "status"):
        r = adm.get(f"/api/reports/{kind}"); assert r.status_code == 200 and r.json()["rows"], kind
    csvr = adm.get("/api/reports/bureau", params={"format": "csv"})
    assert csvr.headers["content-type"].startswith("text/csv") and "Disposal rate" in csvr.text
    assert adm.get("/api/reports/nope").status_code == 404 and client.get("/api/impact").status_code == 401
    i = adm.get("/api/impact", params={"hours_per_duplicate": 4}).json()
    assert i["est_hours_saved"] == i["cross_bureau_pairs"] * 4 and "Estimate" in i["assumption"]


def test_reports_respect_scope(client):
    ro, _ = login(client, "ro.western"); rows = ro.get("/api/reports/region").json()["rows"]
    assert [r[0] for r in rows] == ["Western"]


# ---------------- Phase 5: Gap features (Public Track, Documents, Bulk Import) ----------------
def test_public_track_endpoint(client):
    adm, _ = login(client, "chairman")
    case = adm.get("/api/cases", params={"size": 1}).json()["items"][0]

    # Public user without any credentials
    res = client.get(f"/api/public/track/{case['case_no']}")
    assert res.status_code == 200
    data = res.json()
    assert data["case_no"] == case["case_no"]
    assert "status" in data and "milestones" in data
    assert len(data["milestones"]) >= 1

    # Bad case number gives 404
    bad = client.get("/api/public/track/AICTE-FAKE-99999")
    assert bad.status_code == 404


def test_document_upload_and_download(client):
    c, _ = login(client, "rb.officer1")
    cases = c.get("/api/cases", params={"bureau": "RB", "size": 1}).json()["items"]
    case = cases[0]

    # Upload test document
    doc_content = b"%PDF-1.4 Mock show cause notice content"
    files = {"file": ("notice.pdf", io.BytesIO(doc_content), "application/pdf")}
    res = c.post(f"/api/cases/{case['id']}/documents", files=files, data={"remarks": "Show cause notice issued"})
    assert res.status_code == 200
    filename = res.json()["filename"]
    assert filename.endswith(".pdf")

    # Download document
    down = c.get(f"/api/documents/{filename}")
    assert down.status_code == 200
    assert down.content == doc_content

    # Unauthorized access (invalid filename format)
    assert c.get("/api/documents/bad_traversal_filename").status_code == 400


def test_bulk_csv_import(client):
    adm, _ = login(client, "chairman")

    # 1. Download template
    tmpl = adm.get("/api/cases/import/template")
    assert tmpl.status_code == 200
    assert "institution_ref" in tmpl.text and "fee_refund" in tmpl.text

    # 2. Preview CSV using an existing institution from DB
    inst = adm.get("/api/institutions").json()[0]
    inst_name = inst["name"]
    csv_data = (
        "institution_ref,subject,description,category,bureau,priority,complainant_contact\n"
        f"{inst_name},Salary delayed by 4 months,Teachers have not received salary for 4 months,salary_delay,PGRC,High,prof@test.com\n"
    )
    files = {"file": ("import.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    prev = adm.post("/api/cases/import/preview", files=files)
    assert prev.status_code == 200
    pj = prev.json()
    assert pj["total_rows"] == 1 and pj["valid_rows"] == 1
    item = pj["items"][0]
    assert item["institution_matched"] is not None
    assert item["bureau"] == "PGRC"

    # 3. Commit CSV
    commit = adm.post("/api/cases/import/commit", json={"items": pj["items"]})
    assert commit.status_code == 200
    cj = commit.json()
    assert cj["imported"] == 1
    assert cj["cases"][0]["subject"] == "Salary delayed by 4 months"

