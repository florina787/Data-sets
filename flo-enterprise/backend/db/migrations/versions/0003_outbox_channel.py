"""widen outbox.channel (descriptive mock channel names exceeded 24 chars on PostgreSQL)

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("outbox") as b:
        b.alter_column("channel", type_=sa.String(120), existing_type=sa.String(24))


def downgrade() -> None:
    with op.batch_alter_table("outbox") as b:
        b.alter_column("channel", type_=sa.String(24), existing_type=sa.String(120))
