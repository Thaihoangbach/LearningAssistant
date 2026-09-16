"""Password hashing, JWT issuing/verification, và cookie policy cho
Authentication (docs/auth-spec.md). Tách khỏi app/routers/auth.py để router
chỉ lo HTTP — đổi thuật toán hash/JWT sau này chỉ sửa file này, cùng quy ước
với app/services/document_cleanup.py, app/services/learner_context.py."""

import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
