"""add generation_mode to quizzes and flashcard_sets

Revision ID: f3b8a1d4e6c2
Revises: c3a9f2d81b06
Create Date: 2026-09-10 00:00:00.000000

Learning Loop Phase 0 (xem app/services/learning_state.py,
app/services/learning_policy.py): chuẩn bị chỗ lưu chế độ sinh
("learn"/"review"/"exam"/"weak_topics", Phase 3) ngay từ bây giờ để không
phải migrate schema lần hai. Nullable, không backfill — quiz/flashcard cũ
không có giá trị này.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3b8a1d4e6c2'
down_revision: Union[str, Sequence[str], None] = 'c3a9f2d81b06'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('quizzes', sa.Column('generation_mode', sa.String(), nullable=True))
    op.add_column('flashcard_sets', sa.Column('generation_mode', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('flashcard_sets', 'generation_mode')
    op.drop_column('quizzes', 'generation_mode')
