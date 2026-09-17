"""Password hashing, JWT issuing/verification, và cookie policy cho
Authentication (docs/auth-spec.md). Tách khỏi app/routers/auth.py để router
chỉ lo HTTP — đổi thuật toán hash/JWT sau này chỉ sửa file này, cùng quy ước
với app/services/document_cleanup.py, app/services/learner_context.py."""

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    raise ValueError(
        "Thiếu JWT_SECRET_KEY. Tạo bằng: python -c \"import secrets; "
        "print(secrets.token_hex(32))\" rồi đặt vào .env."
    )
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "10080"))  # 7 ngày


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


# Dùng khi user không tồn tại, để login() vẫn trả bcrypt cost như ca có user —
# tránh timing side-channel lộ email nào đã đăng ký qua thời gian phản hồi
# (xem docs/auth-spec.md mục 8, final review Fix 3). Tính một lần lúc import.
_DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-timing-safety")


def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": user_id, "iat": now, "exp": now + timedelta(minutes=JWT_EXPIRE_MINUTES)}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """Trả user_id (claim `sub`) nếu token hợp lệ, None nếu invalid/expired."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    return payload.get("sub")


def get_cookie_settings(frontend_url: str | None) -> dict:
    """frontend_url có giá trị -> prod, cross-site (frontend/backend khác
    domain) -> cần Secure=True, SameSite="none" để trình duyệt còn gửi cookie.
    Không có -> dev, cả hai đều localhost (cùng site, khác port) ->
    SameSite="lax" đã đủ, Secure=False vì dev chạy http."""
    if frontend_url:
        return {"secure": True, "samesite": "none"}
    return {"secure": False, "samesite": "lax"}
