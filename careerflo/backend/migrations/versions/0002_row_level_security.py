"""Row-level security for Supabase.

Every table has RLS enabled. Direct client access (Supabase anon/authenticated keys) is limited to:
* user-owned rows where ``user_id = auth.uid()`` — full CRUD on personal records,
  **read-only** on metering/billing rows (counters can never be changed from a client);
* read-only access to the public job catalogue, feature catalogue and plans;
* nothing at all on webhook, audit and internal tables.
The FastAPI backend connects with the service role (bypasses RLS) and enforces the same
ownership rules in code. On plain PostgreSQL (no ``auth`` schema) RLS is enabled but policies
that reference ``auth.uid()`` are skipped, so only the table owner (the backend) has access.

Revision ID: 0002
Revises: 0001
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

OWNED_CRUD = ["profiles", "skills", "experience", "education", "user_preferences", "resumes", "resume_versions", "saved_jobs",
              "job_matches", "applications", "application_events", "interviews", "recruiters", "recruiter_interactions",
              "portfolios", "portfolio_projects", "conversations", "messages"]
OWNED_READONLY = ["agent_runs", "mcp_tool_calls", "approval_requests", "audit_events", "inference_metrics", "subscriptions",
                  "stripe_customers", "invoices", "trial_usage", "monthly_usage", "usage_reservations", "usage_events"]
PUBLIC_READ = ["jobs", "job_sources", "employer_boards", "feature_catalog", "feature_entitlements", "subscription_plans"]
PRIVATE = ["users", "stripe_events", "billing_audit_logs", "provider_usage", "search_cache"]


def upgrade() -> None:
    for t in OWNED_CRUD + OWNED_READONLY + PUBLIC_READ + PRIVATE:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
    op.execute("""
    DO $$
    BEGIN
      IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'auth') THEN
        %s
      END IF;
    END $$;
    """ % "\n".join(
        [f"CREATE POLICY {t}_owner_all ON {t} FOR ALL TO authenticated USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());"
         for t in OWNED_CRUD]
        + [f"CREATE POLICY {t}_owner_read ON {t} FOR SELECT TO authenticated USING (user_id = auth.uid());" for t in OWNED_READONLY]
        + [f"CREATE POLICY {t}_read ON {t} FOR SELECT TO authenticated USING (true);" for t in PUBLIC_READ]
        + ["CREATE POLICY users_self_read ON users FOR SELECT TO authenticated USING (id = auth.uid());"]))


def downgrade() -> None:
    for t in OWNED_CRUD + OWNED_READONLY + PUBLIC_READ + PRIVATE:
        op.execute(f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY")
    op.execute("""
    DO $$ DECLARE r record; BEGIN
      FOR r IN SELECT policyname, tablename FROM pg_policies WHERE schemaname = 'public' LOOP
        EXECUTE format('DROP POLICY %I ON %I', r.policyname, r.tablename);
      END LOOP; END $$;""")
