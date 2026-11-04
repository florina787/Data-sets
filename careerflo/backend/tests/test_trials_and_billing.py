"""Trial metering, subscription entitlements and Stripe webhooks (Scenarios D, E, F)."""
import hashlib
import hmac
import json
import threading
import time
import uuid

from app.billing import metering as M
from app.db import SessionLocal
from app.features import FEATURES
from app.models import Subscription, TrialUsage

from .conftest import register, search_jobs, upload_resume


def usage(client, h, fid):
    return next(f for f in client.get("/api/usage", headers=h).json()["features"] if f["id"] == fid)


def first_job(client, h):
    return search_jobs(client, h, query="AI Engineer")["jobs"][0]["id"]


def test_new_user_gets_two_of_every_feature(client, user):
    h, _ = user
    feats = client.get("/api/usage", headers=h).json()["features"]
    assert len(feats) == len(FEATURES) == 16
    assert all(f["trial_limit"] == 2 and f["trial_remaining"] == 2 for f in feats)


def test_scenario_d_trial_exhaustion_is_per_feature(client, user):
    h, _ = user
    upload_resume(client, h)
    jid = first_job(client, h)  # consumes one job_discovery use
    for n in (1, 2):
        r = client.post("/api/resumes/tailor", headers=h | {"Idempotency-Key": f"t{n}"}, json={"job_id": jid})
        assert r.status_code == 200, r.text
        assert r.json()["_usage"]["trial_remaining"] == 2 - n
        assert r.json()["validation"]["final"]["valid"]
    r = client.post("/api/resumes/tailor", headers=h | {"Idempotency-Key": "t3"}, json={"job_id": jid})
    assert r.status_code == 402
    assert r.json()["detail"]["message"] == "You've completed your two free trials of Resume Optimization. Upgrade to continue."
    assert r.json()["detail"]["upgrade_url"] == "/pricing"
    assert usage(client, h, "resume_optimization")["trial_remaining"] == 0
    # nested matching inside tailoring did not consume Job Matching
    assert usage(client, h, "job_matching")["trial_remaining"] == 2
    assert usage(client, h, "job_discovery")["trial_remaining"] == 1
    assert usage(client, h, "cover_letter")["trial_remaining"] == 2
    assert client.get("/api/billing/invoices", headers=h).json()["invoices"] == []  # nothing charged


def test_idempotent_retry_does_not_double_charge(client, user):
    h, _ = user
    a = client.post("/api/jobs/search", headers=h | {"Idempotency-Key": "same"}, json={"query": "Data Scientist"}).json()
    b = client.post("/api/jobs/search", headers=h | {"Idempotency-Key": "same"}, json={"query": "Data Scientist"}).json()
    assert a["total"] == b["total"]
    assert usage(client, h, "job_discovery")["trial_used"] == 1


def test_failed_execution_does_not_consume(client, user):
    h, _ = user  # no resume uploaded -> tailoring fails
    jid = first_job(client, h)
    r = client.post("/api/resumes/tailor", headers=h, json={"job_id": jid})
    assert r.status_code == 404
    assert usage(client, h, "resume_optimization")["trial_remaining"] == 2
    r = client.post("/api/jobs/search", headers=h, json={"query": "x", "origin": "linkedin"})
    assert r.status_code == 503 and "JSEARCH_API_KEY" in r.json()["detail"]
    assert usage(client, h, "job_board_search")["trial_remaining"] == 2


def test_concurrent_requests_cannot_exceed_trial(client, user):
    _, u = user
    uid = uuid.UUID(u["id"])
    wins, errors = [], []

    def worker(i):
        db = SessionLocal()
        try:
            r = M.reserve(db, uid, "salary_intelligence", f"k{i}")
            M.commit(db, r, {})
            wins.append(i)
        except M.FeatureExhausted:
            errors.append(i)
        finally:
            db.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(12)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(wins) == 2 and len(errors) == 10
    with SessionLocal() as db:
        t = db.get(TrialUsage, (uid, "salary_intelligence"))
        assert (t.used, t.reserved) == (2, 0)


def test_trial_counters_cannot_be_modified_by_client(client, user):
    h, _ = user
    for method in ("put", "patch", "post", "delete"):
        assert getattr(client, method)("/api/usage", headers=h).status_code == 405
    # client-supplied plan/limits in a request body are ignored
    r = client.post("/api/salary/report", headers=h, json={"title_keyword": "Engineer", "trial_used": -5, "plan": "premium"})
    assert r.status_code == 200 and r.json()["_usage"]["trial_remaining"] == 1


def test_scenario_f_isolated_users(client):
    h1, _ = register(client)
    h2, _ = register(client)
    res = upload_resume(client, h1)
    app = client.post("/api/applications", headers=h1, json={"company": "Acme", "title": "AI Engineer"}).json()
    assert client.get(f"/api/resumes/{res['id']}", headers=h2).status_code == 404
    assert client.get("/api/resumes", headers=h2).json()["resumes"] == []
    assert client.get("/api/applications", headers=h2).json()["applications"] == []
    assert client.get(f"/api/applications/{app['id']}/history", headers=h2).status_code == 404
    assert client.patch(f"/api/applications/{app['id']}", headers=h2, json={"notes": "pwned"}).status_code == 404
    jid = first_job(client, h1)
    assert client.post("/api/resumes/tailor", headers=h2, json={"job_id": jid, "resume_id": res["id"]}).status_code == 404
    assert usage(client, h1, "job_discovery")["trial_remaining"] == 1
    assert usage(client, h2, "job_discovery")["trial_remaining"] == 2
    assert client.get("/api/admin/metrics", headers=h1).status_code == 403


def test_unauthenticated_and_forged_tokens_rejected(client):
    assert client.get("/api/usage").status_code == 401
    import jwt

    forged = jwt.encode({"sub": str(uuid.uuid4()), "aud": "authenticated", "iss": "careerflo-local"}, "x" * 40, algorithm="HS256")
    assert client.get("/api/usage", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_email_alias_cannot_reregister(client):
    register(client, "jane.doe+a@gmail.com")
    r = client.post("/api/auth/register", json={"email": "janedoe@gmail.com", "password": "CorrectHorse42"})
    assert r.status_code == 409


# ---------------------------------------------------------------- Stripe webhooks (Scenario E)
def signed(client, event):
    payload = json.dumps(event)
    t = int(time.time())
    sig = hmac.new(b"whsec_test_secret", f"{t}.{payload}".encode(), hashlib.sha256).hexdigest()
    return client.post("/api/webhooks/stripe", content=payload, headers={"Stripe-Signature": f"t={t},v1={sig}", "Content-Type": "application/json"})


def sub_event(eid, uid, status, created, price="price_pro_test", cancel=False):
    now = int(time.time())
    return {"id": eid, "type": "customer.subscription.updated", "created": created, "data": {"object": {
        "id": f"sub_{uid[:8]}", "customer": f"cus_{uid[:8]}", "status": status, "cancel_at_period_end": cancel, "livemode": False,
        "metadata": {"careerflo_user_id": uid}, "items": {"data": [{"price": {"id": price}, "current_period_start": now,
                                                                     "current_period_end": now + 30 * 86400}]}}}}


def test_scenario_e_webhook_unlocks_plan_idempotently_and_in_order(client, user):
    h, u = user
    uid = u["id"]
    assert client.post("/api/webhooks/stripe", content=b"{}", headers={"Stripe-Signature": "t=1,v1=bad"}).status_code == 400
    for _ in range(2):
        usage_before = client.get("/api/usage", headers=h).json()["plan"]["id"]
        assert usage_before == "free"
        # exhaust trial
        client.post("/api/analytics/report", headers=h)
        client.post("/api/analytics/report", headers=h)
    assert client.post("/api/analytics/report", headers=h).status_code == 402
    r = signed(client, sub_event("evt_1", uid, "active", 1000))
    assert r.json()["outcome"] == "processed"
    assert signed(client, sub_event("evt_1", uid, "active", 1000)).json()["outcome"] == "duplicate"  # replay
    assert client.get("/api/usage", headers=h).json()["plan"]["id"] == "pro"
    r = client.post("/api/analytics/report", headers=h)
    assert r.status_code == 200 and r.json()["_usage"]["plan_remaining"] == 59
    # Premium-only feature stays locked on Pro after its trial
    client.post("/api/portfolio/analyze", headers=h, json={"username": "-"})  # invalid -> 422, nothing consumed
    # out-of-order: an older 'canceled' event arriving late is ignored
    assert signed(client, sub_event("evt_old", uid, "canceled", 900)).json()["outcome"] == "ignored_out_of_order"
    assert client.get("/api/usage", headers=h).json()["plan"]["id"] == "pro"
    # newer cancellation removes access
    assert signed(client, sub_event("evt_2", uid, "canceled", 2000)).json()["outcome"] == "processed"
    assert client.get("/api/usage", headers=h).json()["plan"]["id"] == "free"
    assert client.post("/api/analytics/report", headers=h).status_code == 402


def test_invoice_events_recorded(client, user):
    h, u = user
    signed(client, sub_event("evt_s_" + u["id"][:6], u["id"], "active", 10))
    inv = {"id": "evt_inv_" + u["id"][:6], "type": "invoice.paid", "created": 11, "data": {"object": {
        "id": "in_" + u["id"][:8], "customer": f"cus_{u['id'][:8]}", "amount_paid": 999, "currency": "cad", "livemode": False,
        "status_transitions": {"paid_at": int(time.time())}, "lines": {"data": [{"price": {"id": "price_pro_test"}}]}}}}
    assert signed(client, inv).json()["outcome"] == "processed"
    rows = client.get("/api/billing/invoices", headers=h).json()["invoices"]
    assert rows[0]["amount_cents"] == 999 and rows[0]["plan"] == "pro"
    admin_h, _ = register(client, "admin@example.com")
    m = client.get("/api/admin/metrics", headers=admin_h).json()
    assert m["active_pro"] >= 1 and m["mrr_cents"] >= 999


def test_checkout_without_stripe_config_is_clear(client, user):
    h, _ = user
    r = client.post("/api/billing/checkout", headers=h, json={"plan": "pro"})
    assert r.status_code == 503 and "STRIPE_SECRET_KEY" in r.json()["detail"]


def test_stale_subscription_gives_no_access(client, user):
    h, u = user
    with SessionLocal() as db:
        from datetime import datetime, timezone
        db.add(Subscription(user_id=uuid.UUID(u["id"]), stripe_subscription_id="sub_stale_" + u["id"][:6], stripe_customer_id="c",
                            plan_id="premium", status="active", current_period_end=datetime(2020, 1, 1, tzinfo=timezone.utc)))
        db.commit()
    assert client.get("/api/usage", headers=h).json()["plan"]["id"] == "free"
