"""add content_type to quiz_items and flashcard_items

Revision ID: d4e8f2a91c37
Revises: a1c7e93fb45d
Create Date: 2026-09-10 00:00:00.000000

Learning Loop Phase 5 (xem app/llm/quiz_generator.py::_build_item_judge_prompt,
app/llm/flashcard_generator.py bản mirror): lưu phân loại của LLM-judge
("concept"/"definition"/"formula"/"fact"/"procedure"). Nullable, không
backfill — câu hỏi/thẻ sinh trước Phase 5 không có giá trị này.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e8f2a91c37'
down_revision: Union[str, Sequence[str], None] = 'a1c7e93fb45d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('quiz_items', sa.Column('content_type', sa.String(), nullable=True))
    op.add_column('flashcard_items', sa.Column('content_type', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('flashcard_items', 'content_type')
    op.drop_column('quiz_items', 'content_type')
