"""make flashcard_sets.document_id nullable

Revision ID: a1c7e93fb45d
Revises: f3b8a1d4e6c2
Create Date: 2026-09-10 00:00:00.000000

Sửa bug: save_from_answer() (app/routers/flashcard.py) lưu thẻ "từ câu trả
lời hỏi đáp/quiz sai" — không gắn tài liệu nào — bằng sentinel string
"saved-from-answers" thay cho document_id thật, vi phạm FK NOT NULL tới
documents.id ngay khi Postgres ép ràng buộc (chưa từng lộ ra vì chưa có test
nào chạy route này trên Postgres thật). Route đã sửa dùng NULL thay sentinel;
cột phải nullable để INSERT đó không còn vỡ FK. Không có dữ liệu cũ cần
backfill — mọi lần gọi route này trước đây đều lỗi 500, không có dòng nào
từng ghi thành công với sentinel cũ.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c7e93fb45d'
down_revision: Union[str, Sequence[str], None] = 'f3b8a1d4e6c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('flashcard_sets', 'document_id', existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('flashcard_sets', 'document_id', existing_type=sa.String(), nullable=False)
