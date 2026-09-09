"""add document content_hash

Revision ID: 1b1e163708f0
Revises: 835b411f101a
Create Date: 2026-09-09 00:00:00.000000

BUG-005: nhận diện tài liệu trùng bằng NỘI DUNG THẬT (SHA-256), không phải
file_name — xem app/models.py::Document.content_hash và
app/routers/documents.py::_hash_bytes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1b1e163708f0'
down_revision: Union[str, Sequence[str], None] = '835b411f101a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('documents', sa.Column('content_hash', sa.String(), nullable=True))
    op.create_index(op.f('ix_documents_content_hash'), 'documents', ['content_hash'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_documents_content_hash'), table_name='documents')
    op.drop_column('documents', 'content_hash')
