"""pgvector embeddings (PostgreSQL only; no-op on SQLite)

Revision ID: 0002
Revises: 0001
"""
from alembic import op
from sqlalchemy import text

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    avail = bind.execute(text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")).scalar()
    if not avail:
        return  # pgvector not installed on this server: retrieval uses the in-process cosine path
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("ALTER TABLE doc_chunks ADD COLUMN IF NOT EXISTS embedding_vec vector(384)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_doc_chunks_embedding_vec ON doc_chunks USING hnsw (embedding_vec vector_cosine_ops)")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_doc_chunks_embedding_vec")
        op.execute("ALTER TABLE doc_chunks DROP COLUMN IF EXISTS embedding_vec")
