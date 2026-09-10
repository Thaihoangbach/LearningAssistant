"""add course_deadlines table and document display_name

Revision ID: c3a9f2d81b06
Revises: 1b1e163708f0
Create Date: 2026-09-09 00:00:00.000000

Kế hoạch ôn đa môn: mỗi môn cần một ngày thi riêng (app/models.py::
CourseDeadline) để tính days_left độc lập từng môn
(app/services/study_planner.py::generate_multi_course_plan). `display_name`
trên documents tách tên hiển thị khỏi tên file OS gốc.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3a9f2d81b06'
down_revision: Union[str, Sequence[str], None] = '1b1e163708f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('documents', sa.Column('display_name', sa.String(), nullable=True))
    op.create_table(
        'course_deadlines',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('course_name', sa.String(), nullable=False),
        sa.Column('exam_date', sa.Date(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'course_name', name='uq_course_deadlines_user_course'),
    )
    op.create_index(
        op.f('ix_course_deadlines_user_id'), 'course_deadlines', ['user_id'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_course_deadlines_user_id'), table_name='course_deadlines')
    op.drop_table('course_deadlines')
    op.drop_column('documents', 'display_name')
