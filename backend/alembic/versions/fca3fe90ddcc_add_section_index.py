"""add section_index to document_chunks and document_topics

Revision ID: fca3fe90ddcc
Revises: d4e8f2a91c37
Create Date: 2026-09-11 00:00:00.000000

Chỉ số 0-based của section (trang PDF / nhóm đoạn văn DOCX) mà một chunk/topic
sinh ra từ đó — app/ingestion/chunker.py::Chunk.section_index và
app/ingestion/outline.py::OutlineEntry.section_index. Dùng để lấy lại đúng dải
chunk thuộc một DocumentTopic theo thứ tự đọc gốc (structural retrieval cho
tính năng Tóm tắt), thay vì truy hồi semantic top-k vốn không phù hợp cho một
yêu cầu "tóm tắt cả chương". Nullable, KHÔNG backfill trong migration này —
chunk/topic của tài liệu tải lên trước khi cột này tồn tại sẽ có giá trị NULL
cho tới khi chạy backfill riêng (tải lại file gốc từ object storage, chạy lại
pipeline ingest).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fca3fe90ddcc'
down_revision: Union[str, Sequence[str], None] = 'd4e8f2a91c37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('document_chunks', sa.Column('section_index', sa.Integer(), nullable=True))
    op.add_column('document_topics', sa.Column('section_index', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('document_topics', 'section_index')
    op.drop_column('document_chunks', 'section_index')
