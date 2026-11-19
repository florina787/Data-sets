"""FLOW WEALTH prediction ledger: append-only market predictions and their outcomes

Revision ID: 0005
Revises: 0004
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

TABLES = ("market_predictions", "market_prediction_outcomes")


def install_immutability(bind) -> None:
    """Reject UPDATE and DELETE at the database level (SQLite and PostgreSQL)."""
    if bind.dialect.name == "sqlite":
        for t in TABLES:
            for op_ in ("UPDATE", "DELETE"):
                bind.exec_driver_sql(f"CREATE TRIGGER IF NOT EXISTS {t}_no_{op_.lower()} BEFORE {op_} ON {t} "
                                     f"BEGIN SELECT RAISE(ABORT, '{t} is append-only'); END;")
    elif bind.dialect.name == "postgresql":
        bind.exec_driver_sql("""CREATE OR REPLACE FUNCTION flo_append_only() RETURNS trigger AS $$
            BEGIN RAISE EXCEPTION '% is append-only', TG_TABLE_NAME; END; $$ LANGUAGE plpgsql;""")
        for t in TABLES:
            bind.exec_driver_sql(f"DROP TRIGGER IF EXISTS {t}_append_only ON {t}")
            bind.exec_driver_sql(f"CREATE TRIGGER {t}_append_only BEFORE UPDATE OR DELETE ON {t} "
                                 f"FOR EACH ROW EXECUTE FUNCTION flo_append_only()")


def upgrade() -> None:
    op.create_table(
        "market_predictions",
        sa.Column("seq", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("id", sa.String(40), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("mode", sa.String(24), nullable=False),
        sa.Column("model_version", sa.String(80), nullable=False),
        sa.Column("dataset_version", sa.String(80), nullable=False),
        sa.Column("ticker", sa.String(16), nullable=False),
        sa.Column("horizon_sessions", sa.Integer(), nullable=False),
        sa.Column("feature_cutoff", sa.DateTime(), nullable=False),
        sa.Column("outcome_due", sa.DateTime(), nullable=False),
        sa.Column("predicted_excess_return", sa.Float(), nullable=True),
        sa.Column("predicted_rank_pct", sa.Float(), nullable=True),
        sa.Column("uncertainty", sa.Float(), nullable=True),
        sa.Column("regime", sa.String(40), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False),
    )
    for c in ("created_at", "mode", "model_version", "ticker", "outcome_due"):
        op.create_index(f"ix_market_predictions_{c}", "market_predictions", [c])
    op.create_table(
        "market_prediction_outcomes",
        sa.Column("prediction_id", sa.String(40), sa.ForeignKey("market_predictions.id"), primary_key=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=False),
        sa.Column("actual_return", sa.Float(), nullable=True),
        sa.Column("benchmark_return", sa.Float(), nullable=True),
        sa.Column("actual_excess_return", sa.Float(), nullable=True),
        sa.Column("direction_correct", sa.Boolean(), nullable=True),
        sa.Column("abs_error", sa.Float(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("source", sa.String(120), nullable=False),
    )
    install_immutability(op.get_bind())


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for t in TABLES:
            bind.exec_driver_sql(f"DROP TRIGGER IF EXISTS {t}_append_only ON {t}")
    op.drop_table("market_prediction_outcomes")
    op.drop_table("market_predictions")
