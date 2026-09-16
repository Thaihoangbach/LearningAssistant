"""add_password_hash_to_users

Revision ID: 22985ddfc278
Revises: fca3fe90ddcc
Create Date: 2026-09-16 22:38:04.297170

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '22985ddfc278'
down_revision: Union[str, Sequence[str], None] = 'fca3fe90ddcc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Bỏ toàn bộ dữ liệu demo-user hiện có (docs/auth-spec.md mục 9) —
    # password_hash NOT NULL không backfill được cho user cũ chưa từng có mật
    # khẩu. Không có FK nào trỏ tới users.id khai báo ondelete=CASCADE (đã
    # verify trong app/models.py) nên TRUNCATE ... CASCADE ở tầng Postgres là
    # cách đúng để dọn sạch, không phụ thuộc cascade của ORM.
    op.execute("TRUNCATE TABLE users CASCADE")
    op.add_column("users", sa.Column("password_hash", sa.String(), nullable=False))


def downgrade() -> None:
    op.drop_column("users", "password_hash")
