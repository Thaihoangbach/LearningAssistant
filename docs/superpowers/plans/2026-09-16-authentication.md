# Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thay `user_id="demo-user"` hardcode bằng đăng nhập thật (email + mật khẩu, JWT trong cookie HttpOnly), và chuyển toàn bộ 8 router hiện có từ nhận `user_id` do client tự khai sang `Depends(get_current_user)`.

**Architecture:** FastAPI dependency tập trung (`get_current_user`) đọc JWT từ cookie, mọi route đổi từ tham số `user_id` sang `current_user: User = Depends(get_current_user)`. Password hash (bcrypt) và JWT (PyJWT) cô lập trong `app/services/auth_service.py`, không rải vào router.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 + Alembic, Postgres (pgvector), `bcrypt`, `PyJWT`, React 18 + react-router-dom 6 (frontend), `unittest` (backend test convention có sẵn, chạy qua `python -m unittest discover -s tests`).

**Spec:** `docs/auth-spec.md` — mọi task dưới đây trace về đúng 1 mục trong spec đó.

## Global Constraints

- Password: 8–64 ký tự (product policy, không phải giới hạn byte của bcrypt) — spec mục 3.
- JWT: HS256, claims chỉ `{sub, iat, exp}` — không có `email` — spec mục 4.
- JWT hết hạn mặc định 7 ngày (10080 phút), đọc từ `JWT_EXPIRE_MINUTES`, secret bắt buộc từ `JWT_SECRET_KEY` (fail-fast nếu thiếu) — spec mục 4.
- Cookie tên `access_token`, `httponly=True`, `path="/"` — Secure/SameSite suy ra từ `FRONTEND_URL` qua `get_cookie_settings()`, không thêm env mới — spec mục 5.
- Hash/verify password và JWT encode/decode chỉ sống trong `app/services/auth_service.py` — router không gọi `bcrypt`/`jwt` trực tiếp — spec mục 3–4.
- Insert-trước-bắt-`IntegrityError` cho email trùng, không check-rồi-insert — spec mục 7.
- Login sai luôn trả cùng 1 message `"Email hoặc mật khẩu không đúng"` bất kể lý do — spec mục 8.
- Không thêm field `is_active`/`is_verified`/CSRF token framework/refresh token — ngoài phạm vi MVP, spec mục 1 và 10.
- **Kỹ thuật test dùng xuyên suốt Phase 3** (áp dụng cho mọi router test): tạo 2 object User riêng biệt trong `setUp` — một `db.add()` + `commit()` thật (để thoả FK của Document/Quiz/...), một object `User(...)` **KHÔNG BAO GIỜ** `db.add()` (transient, không gắn session nào) dùng làm giá trị trả về khi override `get_current_user`. Lý do: `sessionmaker` hiện tại không set `expire_on_commit=False`, nên object đã `commit()` xong sẽ bị SQLAlchemy "expire" — đọc thuộc tính sau khi session đã đóng sẽ ném `DetachedInstanceError`. Object transient không thuộc session nào thì không bị expire, giữ nguyên thuộc tính mãi mãi — an toàn để làm fake `current_user`.
- Frontend hiện KHÔNG có test framework nào (không vitest/jest trong `package.json`) — Phase 4 dùng bước verify thủ công (`npm run dev` + thao tác tay), không bịa ra hạ tầng test JS mới ngoài phạm vi yêu cầu.

---

## File Structure

**Backend — tạo mới:**
- `backend/app/services/auth_service.py` — hash/verify password, JWT encode/decode, `get_cookie_settings()`.
- `backend/app/routers/auth.py` — `get_current_user`, 4 endpoint auth.
- `backend/alembic/versions/<rev>_add_password_hash_to_users.py`
- `tests/test_auth_service.py`, `tests/test_auth_routes.py`, `tests/test_user_model.py`, `tests/test_mastery_route.py`, `tests/test_chat_route.py` (2 file cuối chưa tồn tại — mastery.py/chat.py chưa có test cấp route).

**Backend — sửa:**
- `backend/app/models.py` (thêm `password_hash`)
- `backend/requirements.txt`, `.env.example`
- `backend/app/main.py` (đăng ký router auth)
- `backend/app/database.py` (xoá `ensure_user` ở cuối Phase 3)
- `backend/app/routers/{courses,mastery,profile,study_plan,flashcard,quiz,documents,chat}.py`
- `backend/app/services/context_assembly.py`
- Test đã có, cần sửa: `tests/test_courses_route.py`, `tests/test_documents_route.py`, `tests/test_flashcard_route.py`, `tests/test_profile_route.py`, `tests/test_quiz_route.py`, `tests/test_study_plan_route.py`

**Frontend — tạo mới:**
- `frontend/src/contexts/AuthContext.jsx`
- `frontend/src/pages/LoginPage.jsx`, `frontend/src/pages/RegisterPage.jsx`
- `frontend/src/components/ProtectedRoute.jsx`

**Frontend — sửa:**
- `frontend/src/api.js` (xoá `CURRENT_USER_ID`, thêm `credentials: "include"`, thêm `login/register/logout/getCurrentUser`)
- `frontend/src/main.jsx` (bọc `AuthProvider`)
- `frontend/src/App.jsx` (route `/login`, `/register`, bọc `ProtectedRoute`)
- `frontend/src/components/layout/Topbar.jsx` (nút đăng xuất)

---

## PHASE 1 — Authentication Domain

### Task 1: User model + migration + dependencies

**Files:**
- Modify: `backend/app/models.py:36-45`
- Modify: `backend/requirements.txt`, `.env.example`
- Create: `backend/alembic/versions/<rev>_add_password_hash_to_users.py`
- Test: `tests/test_user_model.py`

**Interfaces:**
- Produces: `User.password_hash` (String, NOT NULL) — mọi task sau dùng field này.

- [ ] **Step 1: Viết test thất bại**

```python
# tests/test_user_model.py
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy.exc import IntegrityError

from app.models import User
from pg_test_helpers import fresh_test_session_factory


class UserModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine, cls.SessionLocal = fresh_test_session_factory()

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def test_password_hash_is_required(self):
        db = self.SessionLocal()
        try:
            db.add(User(id="u1", email="a@test.local", display_name="A"))
            with self.assertRaises(IntegrityError):
                db.commit()
        finally:
            db.rollback()
            db.close()

    def test_user_can_be_created_with_password_hash(self):
        db = self.SessionLocal()
        try:
            db.add(User(id="u2", email="b@test.local", display_name="B", password_hash="hashed"))
            db.commit()
            saved = db.query(User).filter(User.id == "u2").first()
            self.assertEqual(saved.password_hash, "hashed")
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run (từ thư mục gốc repo, Postgres test đã chạy theo README):
```
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/edututor_test TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/edututor_test python -m unittest tests.test_user_model -v
```
Expected: FAIL — `test_password_hash_is_required` không raise `IntegrityError` (cột chưa tồn tại/chưa NOT NULL), `test_user_can_be_created_with_password_hash` FAIL với `TypeError: 'password_hash' is an invalid keyword argument`.

- [ ] **Step 3: Thêm cột vào model**

Sửa `backend/app/models.py` dòng 36-45:
```python
class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    display_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    documents = relationship("Document", back_populates="user")
    conversations = relationship("Conversation", back_populates="user")
```

- [ ] **Step 4: Chạy test, xác nhận PASS**

Run lệnh Step 2 lại. Expected: PASS (2/2) — `fresh_test_session_factory()` dùng `Base.metadata.create_all()` nên schema mới có hiệu lực ngay, không cần Alembic cho test.

- [ ] **Step 5: Thêm dependency vào requirements.txt**

Thêm vào cuối `backend/requirements.txt` (giữ style comment hiện có, không xoá dòng nào):
```
bcrypt==4.2.0
PyJWT==2.9.0
email-validator==2.2.0
```

- [ ] **Step 6: Cài dependency, xác nhận import được**

Run: `pip install -r requirements.txt` (từ thư mục có venv của backend), sau đó `python -c "import bcrypt, jwt; from email_validator import validate_email"`.
Expected: không lỗi import.

- [ ] **Step 7: Thêm biến môi trường vào `.env.example`**

Thêm vào cuối `.env.example`:
```
# ── Authentication (bắt buộc) ────────────────────────────────────────
# Chuỗi bí mật ký JWT — tạo bằng: python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET_KEY=
# Thời hạn JWT (phút). Mặc định 10080 (7 ngày) nếu để trống.
# JWT_EXPIRE_MINUTES=10080
```

- [ ] **Step 8: Tạo migration Alembic**

Run (từ `backend/`): `alembic revision -m "add_password_hash_to_users"`

Sửa nội dung file vừa tạo (giữ nguyên `revision`/`down_revision`/`create_date` mà Alembic tự sinh):
```python
"""add_password_hash_to_users

Revision ID: <giữ nguyên id Alembic đã sinh>
Revises: <giữ nguyên head cũ Alembic đã tự điền>
Create Date: <giữ nguyên>
"""
from alembic import op
import sqlalchemy as sa

revision = "<giữ nguyên>"
down_revision = "<giữ nguyên>"
branch_labels = None
depends_on = None


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
```

- [ ] **Step 9: KHÔNG chạy `alembic upgrade head` trên bất kỳ DB đã deploy/có dữ liệu thật ở bước này.**

Nếu đang có Postgres dev cục bộ trống hoặc chỉ có dữ liệu demo (đúng trường hợp README mô tả), chạy `alembic upgrade head` để xác nhận migration áp dụng được không lỗi. Nếu `DATABASE_URL` đang trỏ vào bất kỳ DB nào có dữ liệu người dùng thật đã deploy (Render/Neon...), DỪNG LẠI và hỏi người dùng xác nhận trước khi chạy — đây là hành động phá huỷ không thể hoàn tác (spec mục 9).

- [ ] **Step 10: Commit**

```bash
git add backend/app/models.py backend/requirements.txt .env.example backend/alembic/versions/ tests/test_user_model.py
git commit -m "feat: them password_hash vao User model + migration"
```

---

### Task 2: Password hashing service

**Files:**
- Create: `backend/app/services/auth_service.py`
- Test: `tests/test_auth_service.py`

**Interfaces:**
- Produces: `hash_password(password: str) -> str`, `verify_password(password: str, password_hash: str) -> bool`.

- [ ] **Step 1: Viết test thất bại**

```python
# tests/test_auth_service.py
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-do-not-use-in-prod")

from app.services.auth_service import hash_password, verify_password


class PasswordHashingTest(unittest.TestCase):
    def test_verify_password_with_correct_password_returns_true(self):
        hashed = hash_password("correct-horse-battery")
        self.assertTrue(verify_password("correct-horse-battery", hashed))

    def test_verify_password_with_wrong_password_returns_false(self):
        hashed = hash_password("correct-horse-battery")
        self.assertFalse(verify_password("wrong-password", hashed))

    def test_hash_password_does_not_return_plaintext(self):
        hashed = hash_password("correct-horse-battery")
        self.assertNotEqual(hashed, "correct-horse-battery")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `JWT_SECRET_KEY=test python -m unittest tests.test_auth_service -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.auth_service'`.

- [ ] **Step 3: Viết implementation tối thiểu (chỉ phần password)**

```python
# backend/app/services/auth_service.py
"""Password hashing, JWT issuing/verification, và cookie policy cho
Authentication (docs/auth-spec.md). Tách khỏi app/routers/auth.py để router
chỉ lo HTTP — đổi thuật toán hash/JWT sau này chỉ sửa file này, cùng quy ước
với app/services/document_cleanup.py, app/services/learner_context.py."""

import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
```

- [ ] **Step 4: Chạy test, xác nhận PASS**

Run lệnh Step 2 lại. Expected: PASS (3/3).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/auth_service.py tests/test_auth_service.py
git commit -m "feat: them password hashing service (bcrypt)"
```

---

### Task 3: JWT + cookie settings

**Files:**
- Modify: `backend/app/services/auth_service.py`
- Test: `tests/test_auth_service.py`

**Interfaces:**
- Consumes: file đã có `hash_password`/`verify_password` (Task 2).
- Produces: `create_access_token(user_id: str) -> str`, `decode_access_token(token: str) -> str | None`, `get_cookie_settings(frontend_url: str | None) -> dict`, hằng số `JWT_EXPIRE_MINUTES`, `JWT_ALGORITHM`, `JWT_SECRET_KEY` — dùng ở Task 4-6 (`app/routers/auth.py`).

- [ ] **Step 1: Viết test thất bại**

Thêm vào cuối `tests/test_auth_service.py` (trước `if __name__`):
```python
from datetime import datetime, timedelta, timezone

from app.services.auth_service import (
    create_access_token,
    decode_access_token,
    get_cookie_settings,
)


class JWTTest(unittest.TestCase):
    def test_decode_access_token_returns_user_id_from_valid_token(self):
        token = create_access_token("user-123")
        self.assertEqual(decode_access_token(token), "user-123")

    def test_decode_access_token_returns_none_for_garbage_token(self):
        self.assertIsNone(decode_access_token("not-a-real-token"))

    def test_decode_access_token_returns_none_for_expired_token(self):
        import jwt as pyjwt
        from app.services.auth_service import JWT_ALGORITHM, JWT_SECRET_KEY

        expired_payload = {
            "sub": "user-123",
            "iat": datetime.now(timezone.utc) - timedelta(days=8),
            "exp": datetime.now(timezone.utc) - timedelta(days=1),
        }
        expired_token = pyjwt.encode(expired_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        self.assertIsNone(decode_access_token(expired_token))


class CookieSettingsTest(unittest.TestCase):
    def test_no_frontend_url_returns_dev_settings(self):
        self.assertEqual(get_cookie_settings(None), {"secure": False, "samesite": "lax"})

    def test_frontend_url_set_returns_prod_settings(self):
        self.assertEqual(
            get_cookie_settings("https://edututor.example.com"),
            {"secure": True, "samesite": "none"},
        )
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `JWT_SECRET_KEY=test python -m unittest tests.test_auth_service -v`
Expected: FAIL — `ImportError: cannot import name 'create_access_token'`.

- [ ] **Step 3: Viết implementation**

Thêm vào đầu và cuối `backend/app/services/auth_service.py`:
```python
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


def hash_password(password: str) -> str:
    ...  # giữ nguyên Task 2


def verify_password(password: str, password_hash: str) -> bool:
    ...  # giữ nguyên Task 2


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
```

(Giữ nguyên thân 2 hàm `hash_password`/`verify_password` đã viết ở Task 2 — chỉ thêm import `os`, `datetime`, `jwt` và phần JWT/cookie ở trên/dưới.)

- [ ] **Step 4: Chạy test, xác nhận PASS**

Run: `JWT_SECRET_KEY=test python -m unittest tests.test_auth_service -v`
Expected: PASS (8/8 — 3 password + 3 JWT + 2 cookie).

- [ ] **Step 5: Xác nhận fail-fast khi thiếu JWT_SECRET_KEY**

Run: `python -c "import sys; sys.path.insert(0, 'backend'); import app.services.auth_service"` (không set `JWT_SECRET_KEY`).
Expected: `ValueError: Thiếu JWT_SECRET_KEY...`

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/auth_service.py tests/test_auth_service.py
git commit -m "feat: them JWT issuing/verification va cookie settings helper"
```

---

## PHASE 2 — Auth API

### Task 4: POST /auth/register

**Files:**
- Create: `backend/app/routers/auth.py`
- Modify: `backend/app/main.py:19-28,72-79`
- Test: `tests/test_auth_routes.py`

**Interfaces:**
- Consumes: `hash_password`, `create_access_token`, `get_cookie_settings`, `JWT_EXPIRE_MINUTES` từ `app.services.auth_service` (Task 2-3).
- Produces: `router` (APIRouter, prefix `/auth`) — Task 5-7 thêm route vào cùng `router` này. `UserOut` schema, `COOKIE_NAME = "access_token"` — dùng lại ở Task 5-6.

- [ ] **Step 1: Viết test thất bại**

```python
# tests/test_auth_routes.py
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-do-not-use-in-prod")

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from pg_test_helpers import fresh_test_session_factory


class RegisterRouteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine, cls.SessionLocal = fresh_test_session_factory()

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.addCleanup(app.dependency_overrides.clear)

    def test_register_with_new_email_returns_201_and_sets_cookie(self):
        res = self.client.post(
            "/auth/register",
            json={"email": "Bach@Example.com", "password": "matkhau123", "display_name": "Bách"},
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["email"], "bach@example.com")
        self.assertNotIn("password_hash", res.json())
        self.assertIn("access_token", res.cookies)

    def test_register_with_duplicate_email_returns_409(self):
        payload = {"email": "dup@example.com", "password": "matkhau123", "display_name": "A"}
        self.client.post("/auth/register", json=payload)
        res = self.client.post("/auth/register", json=payload)
        self.assertEqual(res.status_code, 409)

    def test_register_with_short_password_returns_422(self):
        res = self.client.post(
            "/auth/register",
            json={"email": "short@example.com", "password": "abc", "display_name": "A"},
        )
        self.assertEqual(res.status_code, 422)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `JWT_SECRET_KEY=test DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/edututor_test TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/edututor_test python -m unittest tests.test_auth_routes -v`
Expected: FAIL — `404 Not Found` (chưa có route `/auth/register`).

- [ ] **Step 3: Viết implementation**

```python
# backend/app/routers/auth.py
"""API routes cho Authentication (docs/auth-spec.md) — register/login/logout/me."""

import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services.auth_service import (
    JWT_EXPIRE_MINUTES,
    create_access_token,
    decode_access_token,
    get_cookie_settings,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_NAME = "access_token"
FRONTEND_URL = os.getenv("FRONTEND_URL")


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


def _set_auth_cookie(response: Response, user_id: str) -> None:
    token = create_access_token(user_id)
    settings = get_cookie_settings(FRONTEND_URL)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        path="/",
        max_age=JWT_EXPIRE_MINUTES * 60,
        secure=settings["secure"],
        samesite=settings["samesite"],
    )


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=64)
    display_name: str = Field(min_length=1, max_length=100)


@router.post("/register", status_code=201, response_model=UserOut)
def register(req: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    user = User(
        email=req.email.strip().lower(),
        password_hash=hash_password(req.password),
        display_name=req.display_name.strip(),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Email đã được đăng ký")

    db.refresh(user)
    _set_auth_cookie(response, user.id)
    return user
```

Đăng ký router vào `backend/app/main.py`: thêm `auth` vào import (dòng 19-28):
```python
from app.routers import (
    auth,
    chat,
    courses,
    documents,
    flashcard,
    mastery,
    profile,
    quiz,
    study_plan,
)
```
và thêm dòng include (cạnh dòng 72-79):
```python
app.include_router(auth.router)
app.include_router(documents.router)
...
```

- [ ] **Step 4: Chạy test, xác nhận PASS**

Run lệnh Step 2 lại. Expected: PASS (3/3).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/auth.py backend/app/main.py tests/test_auth_routes.py
git commit -m "feat: them POST /auth/register"
```

---

### Task 5: POST /auth/login

**Files:**
- Modify: `backend/app/routers/auth.py`
- Test: `tests/test_auth_routes.py`

**Interfaces:**
- Consumes: `UserOut`, `_set_auth_cookie`, `verify_password` (Task 2, 4).

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_auth_routes.py` (class mới, trước `if __name__`):
```python
class LoginRouteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine, cls.SessionLocal = fresh_test_session_factory()

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.addCleanup(app.dependency_overrides.clear)
        self.client.post(
            "/auth/register",
            json={"email": "login@example.com", "password": "matkhau123", "display_name": "A"},
        )
        self.client.cookies.clear()

    def test_login_with_correct_credentials_returns_200_and_sets_cookie(self):
        res = self.client.post(
            "/auth/login", json={"email": "login@example.com", "password": "matkhau123"}
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("access_token", res.cookies)

    def test_login_with_wrong_password_returns_401_generic_message(self):
        res = self.client.post(
            "/auth/login", json={"email": "login@example.com", "password": "sai-mat-khau"}
        )
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["detail"], "Email hoặc mật khẩu không đúng")

    def test_login_with_nonexistent_email_returns_same_401_message(self):
        res = self.client.post(
            "/auth/login", json={"email": "khong-ton-tai@example.com", "password": "matkhau123"}
        )
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["detail"], "Email hoặc mật khẩu không đúng")
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: lệnh như Task 4 Step 2, target `tests.test_auth_routes.LoginRouteTest`.
Expected: FAIL — `404 Not Found` (chưa có route `/auth/login`).

- [ ] **Step 3: Viết implementation**

Thêm vào cuối `backend/app/routers/auth.py`:
```python
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/login", response_model=UserOut)
def login(req: LoginRequest, response: Response, db: Session = Depends(get_db)):
    email = req.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(401, "Email hoặc mật khẩu không đúng")

    _set_auth_cookie(response, user.id)
    return user
```

- [ ] **Step 4: Chạy test, xác nhận PASS**

Run lệnh Step 2 lại (cả file). Expected: PASS (6/6).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/auth.py tests/test_auth_routes.py
git commit -m "feat: them POST /auth/login"
```

---

### Task 6: get_current_user + POST /auth/logout + GET /auth/me

**Files:**
- Modify: `backend/app/routers/auth.py`
- Test: `tests/test_auth_routes.py`

**Interfaces:**
- Produces: `get_current_user(request: Request, db: Session = Depends(get_db)) -> User` — **đây là dependency mọi router ở Phase 3 sẽ import** (`from app.routers.auth import get_current_user`).

- [ ] **Step 1: Viết test thất bại**

Thêm vào `tests/test_auth_routes.py`:
```python
class MeAndLogoutRouteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine, cls.SessionLocal = fresh_test_session_factory()

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.addCleanup(app.dependency_overrides.clear)
        self.client.post(
            "/auth/register",
            json={"email": "me@example.com", "password": "matkhau123", "display_name": "A"},
        )

    def test_me_without_cookie_returns_401(self):
        self.client.cookies.clear()
        res = self.client.get("/auth/me")
        self.assertEqual(res.status_code, 401)

    def test_me_with_valid_cookie_returns_current_user(self):
        res = self.client.get("/auth/me")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["email"], "me@example.com")

    def test_logout_then_me_returns_401(self):
        logout_res = self.client.post("/auth/logout")
        self.assertEqual(logout_res.status_code, 204)

        res = self.client.get("/auth/me")
        self.assertEqual(res.status_code, 401)
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run tương tự Task 4 Step 2, target `tests.test_auth_routes.MeAndLogoutRouteTest`.
Expected: FAIL — `404 Not Found`.

- [ ] **Step 3: Viết implementation**

Thêm vào `backend/app/routers/auth.py`, ngay sau `_set_auth_cookie`:
```python
def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401, "Chưa đăng nhập")

    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(401, "Chưa đăng nhập")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(401, "Chưa đăng nhập")
    return user
```

Thêm vào cuối file:
```python
@router.post("/logout", status_code=204)
def logout(response: Response, current_user: User = Depends(get_current_user)):
    settings = get_cookie_settings(FRONTEND_URL)
    response.delete_cookie(
        key=COOKIE_NAME, path="/", secure=settings["secure"], samesite=settings["samesite"]
    )


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
```

- [ ] **Step 4: Chạy test, xác nhận PASS**

Run lệnh Step 2 lại (cả file `test_auth_routes.py`). Expected: PASS (9/9).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/auth.py tests/test_auth_routes.py
git commit -m "feat: them get_current_user, POST /auth/logout, GET /auth/me"
```

Phase 2 hoàn tất — acceptance criteria mục 1-8 của `docs/auth-spec.md` đã có test bao phủ.

---

## PHASE 3 — Security Migration (8 router hiện có -> Depends(get_current_user))

Với mỗi router: xoá tham số `user_id`/field `user_id` trong Pydantic request, thay bằng `current_user: User = Depends(get_current_user)` + `from app.routers.auth import get_current_user` + `from app.models import User`, dùng `current_user.id` ở mọi nơi trước đó dùng `user_id`/`req.user_id`.

### Task 7: courses.py

**Files:**
- Modify: `backend/app/routers/courses.py`
- Modify: `tests/test_courses_route.py`

**Interfaces:**
- Consumes: `get_current_user` (Task 6).

- [ ] **Step 1: Sửa test để dùng dependency override thay vì `user_id` param**

Sửa `tests/test_courses_route.py`:
```python
from app.database import get_db
from app.main import app
from app.models import CourseDeadline, Document, User
from app.routers.auth import get_current_user
from pg_test_helpers import fresh_test_session_factory


class CoursesRouteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine, cls.SessionLocal = fresh_test_session_factory()

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        self.user_id = str(uuid.uuid4())
        db = self.SessionLocal()
        try:
            db.add(User(id=self.user_id, email=f"{self.user_id}@test.local", password_hash="x", display_name="Hoa"))
            db.flush()
            db.add(Document(user_id=self.user_id, file_name="a.pdf", course_name="CSDL", status="sẵn sàng"))
            db.add(Document(user_id=self.user_id, file_name="b.pdf", course_name="CSDL", status="sẵn sàng"))
            db.add(Document(user_id=self.user_id, file_name="c.pdf", course_name="Mạng máy tính", status="sẵn sàng"))
            db.add(Document(user_id=self.user_id, file_name="loose.pdf", course_name=None, status="sẵn sàng"))
            db.commit()
        finally:
            db.close()

        self.current_user = User(
            id=self.user_id, email=f"{self.user_id}@test.local", password_hash="x", display_name="Hoa"
        )
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: self.current_user
        self.client = TestClient(app)
        self.addCleanup(app.dependency_overrides.clear)

    def test_lists_distinct_course_names_excluding_null(self):
        res = self.client.get("/courses")
        self.assertEqual(res.status_code, 200)
        names = [c["course_name"] for c in res.json()["courses"]]
        self.assertEqual(sorted(names), ["CSDL", "Mạng máy tính"])

    def test_course_without_exam_date_has_null_exam_date(self):
        res = self.client.get("/courses")
        by_name = {c["course_name"]: c["exam_date"] for c in res.json()["courses"]}
        self.assertIsNone(by_name["CSDL"])

    def test_set_exam_date_then_list_reflects_it(self):
        put_res = self.client.put("/courses/CSDL/exam-date", json={"exam_date": "2026-12-20"})
        self.assertEqual(put_res.status_code, 200)

        res = self.client.get("/courses")
        by_name = {c["course_name"]: c["exam_date"] for c in res.json()["courses"]}
        self.assertEqual(by_name["CSDL"], "2026-12-20")

    def test_setting_exam_date_twice_updates_instead_of_duplicating(self):
        self.client.put("/courses/CSDL/exam-date", json={"exam_date": "2026-12-20"})
        self.client.put("/courses/CSDL/exam-date", json={"exam_date": "2026-12-25"})

        db = self.SessionLocal()
        try:
            rows = db.query(CourseDeadline).filter(
                CourseDeadline.user_id == self.user_id, CourseDeadline.course_name == "CSDL"
            ).all()
        finally:
            db.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].exam_date, date(2026, 12, 25))

    def test_delete_exam_date_removes_it(self):
        self.client.put("/courses/CSDL/exam-date", json={"exam_date": "2026-12-20"})
        del_res = self.client.delete("/courses/CSDL/exam-date")
        self.assertEqual(del_res.status_code, 200)
        res = self.client.get("/courses")
        by_name = {c["course_name"]: c["exam_date"] for c in res.json()["courses"]}
        self.assertIsNone(by_name["CSDL"])

    def test_delete_exam_date_that_was_never_set_is_404(self):
        res = self.client.delete("/courses/Mạng máy tính/exam-date")
        self.assertEqual(res.status_code, 404)
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `JWT_SECRET_KEY=test DATABASE_URL=... TEST_DATABASE_URL=... python -m unittest tests.test_courses_route -v`
Expected: FAIL — route vẫn đòi `user_id` query/body bắt buộc (422 Unprocessable Entity vì thiếu field required cũ, hoặc route đọc `user_id=None`).

- [ ] **Step 3: Sửa router**

Sửa `backend/app/routers/courses.py`:
```python
from app.database import get_db
from app.models import CourseDeadline, Document, User
from app.routers.auth import get_current_user

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("")
def list_courses(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    course_names = {
        c
        for (c,) in db.query(Document.course_name)
        .filter(Document.user_id == current_user.id, Document.course_name.isnot(None))
        .distinct()
        .all()
    }
    deadlines = {
        d.course_name: d.exam_date
        for d in db.query(CourseDeadline).filter(CourseDeadline.user_id == current_user.id).all()
    }
    return {
        "courses": [
            {
                "course_name": name,
                "exam_date": deadlines[name].isoformat() if name in deadlines else None,
            }
            for name in sorted(course_names)
        ]
    }


class SetExamDateRequest(BaseModel):
    exam_date: date


@router.put("/{course_name}/exam-date")
def set_exam_date(
    course_name: str,
    req: SetExamDateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = insert(CourseDeadline).values(
        user_id=current_user.id, course_name=course_name, exam_date=req.exam_date
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_course_deadlines_user_course",
        set_={"exam_date": stmt.excluded.exam_date, "updated_at": datetime.utcnow()},
    )
    db.execute(stmt)
    db.commit()
    return {"course_name": course_name, "exam_date": req.exam_date.isoformat()}


@router.delete("/{course_name}/exam-date")
def delete_exam_date(
    course_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    deleted = (
        db.query(CourseDeadline)
        .filter(CourseDeadline.user_id == current_user.id, CourseDeadline.course_name == course_name)
        .delete()
    )
    db.commit()
    if not deleted:
        raise HTTPException(404, "Môn học này chưa có ngày thi để xoá.")
    return {"status": "deleted", "course_name": course_name}
```

Xoá `ensure_user` khỏi import dòng 18 (`from app.database import ensure_user, get_db` -> `from app.database import get_db`) — user chắc chắn đã tồn tại (đã đăng nhập qua `get_current_user`), không cần tạo ngầm nữa.

- [ ] **Step 4: Chạy test, xác nhận PASS**

Run lệnh Step 2 lại. Expected: PASS (6/6).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/courses.py tests/test_courses_route.py
git commit -m "refactor: courses.py dung Depends(get_current_user) thay user_id"
```

---

### Task 8: mastery.py (chưa có test cấp route — tạo mới)

**Files:**
- Modify: `backend/app/routers/mastery.py`
- Create: `tests/test_mastery_route.py`

- [ ] **Step 1: Viết test thất bại**

```python
# tests/test_mastery_route.py
"""Integration test cho GET /mastery, /mastery/mistakes — trước đây router
này chỉ có unit test cho service (tests/test_mastery.py), chưa có test cấp
route qua TestClient."""
import os
import sys
import unittest
import uuid
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import Attempt, MasteryScore, Quiz, QuizItem, Topic, User
from app.routers.auth import get_current_user
from pg_test_helpers import fresh_test_session_factory


class MasteryRouteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine, cls.SessionLocal = fresh_test_session_factory()

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        self.user_id = str(uuid.uuid4())
        self.other_user_id = str(uuid.uuid4())
        db = self.SessionLocal()
        try:
            db.add(User(id=self.user_id, email=f"{self.user_id}@test.local", password_hash="x", display_name="Hoa"))
            db.add(User(id=self.other_user_id, email=f"{self.other_user_id}@test.local", password_hash="x", display_name="Khac"))
            db.flush()
            topic = Topic(user_id=self.user_id, name="Chuẩn hoá CSDL", course_name="CSDL")
            db.add(topic)
            db.flush()
            db.add(MasteryScore(user_id=self.user_id, topic_id=topic.id, score=0.4, updated_at=datetime.utcnow()))
            quiz = Quiz(user_id=self.user_id)
            db.add(quiz)
            db.flush()
            item = QuizItem(
                quiz_id=quiz.id, topic_id=topic.id, question="Q1?", options="[]",
                correct_answer="A", explanation="vì A đúng",
            )
            db.add(item)
            db.flush()
            db.add(Attempt(user_id=self.user_id, quiz_item_id=item.id, topic_id=topic.id, is_correct=False, selected_answer="B"))
            db.commit()
        finally:
            db.close()

        self.current_user = User(
            id=self.user_id, email=f"{self.user_id}@test.local", password_hash="x", display_name="Hoa"
        )
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: self.current_user
        self.client = TestClient(app)
        self.addCleanup(app.dependency_overrides.clear)

    def test_get_mastery_returns_only_current_user_topics(self):
        res = self.client.get("/mastery")
        self.assertEqual(res.status_code, 200)
        names = [t["topic_name"] for t in res.json()["topics"]]
        self.assertEqual(names, ["Chuẩn hoá CSDL"])

    def test_get_mistakes_returns_wrong_attempt(self):
        res = self.client.get("/mastery/mistakes")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()["mistakes"]), 1)
        self.assertEqual(res.json()["mistakes"][0]["question"], "Q1?")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `JWT_SECRET_KEY=test DATABASE_URL=... TEST_DATABASE_URL=... python -m unittest tests.test_mastery_route -v`
Expected: FAIL — route đọc `user_id` từ query param (thiếu -> 422).

- [ ] **Step 3: Sửa router**

Sửa `backend/app/routers/mastery.py`:
```python
from app.database import get_db
from app.models import Attempt, Document, MasteryScore, Quiz, QuizItem, Topic, User
from app.routers.auth import get_current_user
from app.services.flashcard import count_due
from app.services.mastery import classify_mastery, decay_unpractised

router = APIRouter(prefix="/mastery", tags=["mastery"])


@router.get("")
def get_mastery(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user_id = current_user.id
    scores = (
        db.query(MasteryScore, Topic)
        .join(Topic, MasteryScore.topic_id == Topic.id)
        .filter(MasteryScore.user_id == user_id)
        .order_by(MasteryScore.score.asc())
        .all()
    )
    # ... (thân hàm giữ nguyên y hệt, chỉ khác nguồn user_id ở dòng trên)


@router.get("/mistakes")
def get_mistakes(
    limit: int = MAX_MISTAKES_RETURNED,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id
    rows = (
        db.query(Attempt, QuizItem)
        .join(QuizItem, Attempt.quiz_item_id == QuizItem.id)
        .filter(Attempt.user_id == user_id, Attempt.is_correct == False)  # noqa: E712
        .order_by(Attempt.attempted_at.desc())
        .limit(limit)
        .all()
    )
    # ... (thân hàm giữ nguyên y hệt)
```

(Toàn bộ thân 2 hàm giữ nguyên logic cũ — chỉ đổi chữ ký hàm và thêm dòng `user_id = current_user.id` ngay đầu mỗi hàm để phần thân bên dưới không cần sửa gì thêm.)

- [ ] **Step 4: Chạy test, xác nhận PASS**

Run lệnh Step 2 lại. Expected: PASS (2/2).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/mastery.py tests/test_mastery_route.py
git commit -m "refactor: mastery.py dung Depends(get_current_user), them route test"
```

---

### Task 9: profile.py

**Files:**
- Modify: `backend/app/routers/profile.py`
- Test: `tests/test_profile_route.py` (sửa theo cùng pattern Task 7 — đọc file hiện có trước khi sửa, áp dụng: bỏ `user_id` khỏi mọi `params`/`json` trong test, thêm `app.dependency_overrides[get_current_user] = lambda: self.current_user` trong `setUp`, tạo `self.current_user` transient như Task 7 Step 1).

- [ ] **Step 1: Sửa test theo pattern Task 7** (đọc `tests/test_profile_route.py` hiện có, áp dụng đúng kỹ thuật override đã dùng ở Task 7/8: thay `user_id` param bằng override `get_current_user`).

- [ ] **Step 2: Chạy test, xác nhận FAIL** — route vẫn đòi `user_id`.

- [ ] **Step 3: Sửa router**

Sửa `backend/app/routers/profile.py`:
```python
from app.database import get_db
from app.llm.guardrail import BLOCKED_MESSAGE, contains_hard_block_pattern
from app.models import LearningProfile, MasteryScore, User
from app.routers.auth import get_current_user
from app.services.learning_profile import infer_level_from_mastery, resolve_effective_level
from app.services.mastery import decay_unpractised

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("")
def get_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user_id = current_user.id
    profile = db.query(LearningProfile).filter(LearningProfile.user_id == user_id).first()
    # ... (thân hàm giữ nguyên)


class UpdateProfileRequest(BaseModel):
    preferred_level: str | None = None
    learning_goal: str | None = None


@router.put("")
def update_profile(
    req: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if req.learning_goal and contains_hard_block_pattern(req.learning_goal):
        raise HTTPException(400, BLOCKED_MESSAGE)

    profile = db.query(LearningProfile).filter(LearningProfile.user_id == current_user.id).first()
    if profile:
        if req.preferred_level is not None:
            profile.preferred_level = req.preferred_level
        if req.learning_goal is not None:
            profile.learning_goal = req.learning_goal
        profile.updated_at = datetime.utcnow()
    else:
        profile = LearningProfile(
            user_id=current_user.id,
            preferred_level=req.preferred_level,
            learning_goal=req.learning_goal,
        )
        db.add(profile)
    db.commit()

    return {
        "preferred_level": profile.preferred_level,
        "learning_goal": profile.learning_goal,
        "updated_at": profile.updated_at.isoformat(),
    }


@router.delete("")
def reset_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(LearningProfile).filter(LearningProfile.user_id == current_user.id).first()
    if profile:
        db.delete(profile)
        db.commit()
    return {"status": "reset"}
```

Xoá `ensure_user` khỏi import (dòng 20) — không còn gọi trong `update_profile`.

- [ ] **Step 4: Chạy test, xác nhận PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/profile.py tests/test_profile_route.py
git commit -m "refactor: profile.py dung Depends(get_current_user) thay user_id"
```

---

### Task 10: study_plan.py

**Files:**
- Modify: `backend/app/routers/study_plan.py`
- Test: `tests/test_study_plan_route.py` (sửa theo cùng pattern Task 7).

- [ ] **Step 1: Sửa test theo pattern Task 7.**

- [ ] **Step 2: Chạy test, xác nhận FAIL.**

- [ ] **Step 3: Sửa router**

Sửa `backend/app/routers/study_plan.py`:
```python
from app.database import get_db
from app.ingestion.outline import filter_topic_titles
from app.memory.service import record_event
from app.models import CourseDeadline, Document, DocumentTopic, MasteryScore, MemoryEvent, Topic, User
from app.routers.auth import get_current_user
from app.services.learning_policy import recommend_action
from app.services.learning_state import get_learning_states
from app.services.mastery import decay_unpractised
from app.services.study_planner import CoursePlanInput, TopicPriority, generate_multi_course_plan

router = APIRouter(prefix="/study-plan", tags=["study-plan"])


@router.get("")
def get_study_plan(
    course_names: list[str] = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id
    course_names = list(dict.fromkeys(course_names))
    # ... (thân hàm giữ nguyên y hệt, đã dùng biến `user_id` cục bộ)


def _topics_reviewed_today(db: Session, user_id: str) -> set[str]:
    # giữ nguyên — vẫn nhận user_id làm tham số, chỉ caller đổi nguồn giá trị
    ...


class MarkReviewedRequest(BaseModel):
    topic_name: str
    course_name: str | None = None


@router.post("/review")
def mark_topic_reviewed(
    req: MarkReviewedRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    topic = (
        db.query(Topic)
        .filter(
            Topic.user_id == current_user.id,
            Topic.course_name == req.course_name,
            Topic.name == req.topic_name,
        )
        .first()
    )
    if not topic:
        raise HTTPException(404, "Không tìm thấy chủ đề này.")

    record_event(
        db,
        user_id=current_user.id,
        event_type=TOPIC_REVIEWED_EVENT_TYPE,
        content=f"Đã tự đánh dấu ôn xong chủ đề \"{topic.name}\"",
        topic_id=topic.id,
    )
    return {"status": "recorded", "topic_name": topic.name}
```

(`get_study_plan` giữ nguyên toàn bộ thân hàm gốc dòng 41-164 — chỉ chữ ký hàm đổi, vì thân hàm đã dùng biến cục bộ `user_id` sẵn từ tham số cũ.)

- [ ] **Step 4: Chạy test, xác nhận PASS.**

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/study_plan.py tests/test_study_plan_route.py
git commit -m "refactor: study_plan.py dung Depends(get_current_user) thay user_id"
```

---

### Task 11: flashcard.py

**Files:**
- Modify: `backend/app/routers/flashcard.py`
- Test: `tests/test_flashcard_route.py` (sửa theo pattern Task 7).

- [ ] **Step 1: Sửa test theo pattern Task 7** — 5 request body/param có `user_id` (`GenerateFlashcardRequest`, `SaveFlashcardRequest`, `ReviewFlashcardRequest`, `list_due`, `get_board`, `get_mistakes`, `get_history`) đều bỏ field `user_id`, dùng override `get_current_user`.

- [ ] **Step 2: Chạy test, xác nhận FAIL.**

- [ ] **Step 3: Sửa router**

Sửa `backend/app/routers/flashcard.py` — 3 Pydantic model bỏ field `user_id`, 7 hàm route thêm `current_user: User = Depends(get_current_user)`, thay mọi `req.user_id`/`user_id` param bằng `current_user.id`:
```python
from app.database import get_db
from app.models import Document, FlashcardItem, FlashcardReview, FlashcardSet, Topic, User
from app.routers.auth import get_current_user

router = APIRouter(prefix="/flashcard", tags=["flashcard"])


class GenerateFlashcardRequest(BaseModel):
    document_id: str
    topic_name: str | None = None
    num_cards: int = 10
    generation_mode: str | None = None


@router.post("/generate")
def generate(
    req: GenerateFlashcardRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id
    if req.generation_mode is not None and req.generation_mode not in VALID_GENERATION_MODES:
        raise HTTPException(400, f"Chế độ sinh không hợp lệ. Chỉ nhận: {', '.join(VALID_GENERATION_MODES)}.")

    doc = (
        db.query(Document)
        .filter(Document.id == req.document_id, Document.user_id == user_id, Document.status == "sẵn sàng")
        .first()
    )
    # ... (thân hàm còn lại giữ nguyên, đã dùng biến cục bộ `user_id`)


class SaveFlashcardRequest(BaseModel):
    front: str
    back: str
    source_document: str | None = None
    source_position: str | None = None
    topic_name: str | None = None


@router.post("/save")
def save_from_answer(
    req: SaveFlashcardRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id
    if not req.front.strip() or not req.back.strip():
        raise HTTPException(400, "Thẻ phải có cả mặt trước và mặt sau.")
    # ... (thân hàm còn lại giữ nguyên)


@router.get("/due")
def list_due(limit: int = 20, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = due_items(db, current_user.id, limit=limit)
    return {"items": [_serialize_item(item, review) for item, review in items]}


@router.get("/board")
def get_board(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    buckets = board(db, current_user.id)
    return {
        status: {"count": len(pairs), "items": [_serialize_item(item, review) for item, review in pairs]}
        for status, pairs in buckets.items()
    }


@router.get("/mistakes")
def get_mistakes(
    limit: int = MAX_MISTAKES_RETURNED,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id
    latest = latest_review_by_item(db, user_id)
    # ... (thân hàm còn lại giữ nguyên)


@router.get("/{item_id}/history")
def get_history(item_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user_id = current_user.id
    item = (
        db.query(FlashcardItem)
        .join(FlashcardSet, FlashcardItem.flashcard_set_id == FlashcardSet.id)
        .filter(FlashcardItem.id == item_id, FlashcardSet.user_id == user_id)
        .first()
    )
    # ... (thân hàm còn lại giữ nguyên)


class ReviewFlashcardRequest(BaseModel):
    flashcard_item_id: str
    rating: str


@router.post("/review")
def review(
    req: ReviewFlashcardRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id
    if req.rating not in VALID_RATINGS:
        raise HTTPException(400, f"Mức đánh giá không hợp lệ. Chỉ nhận: {', '.join(VALID_RATINGS)}.")
    # ... (thân hàm còn lại giữ nguyên, thay mọi req.user_id bằng user_id)
```

- [ ] **Step 4: Chạy test, xác nhận PASS.**

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/flashcard.py tests/test_flashcard_route.py
git commit -m "refactor: flashcard.py dung Depends(get_current_user) thay user_id"
```

---

### Task 12: quiz.py

**Files:**
- Modify: `backend/app/routers/quiz.py`
- Test: `tests/test_quiz_route.py` (sửa theo pattern Task 7).

- [ ] **Step 1: Sửa test theo pattern Task 7** — bỏ `user_id` khỏi `GenerateQuizRequest`/`SubmitAttemptRequest` payload trong test.

- [ ] **Step 2: Chạy test, xác nhận FAIL.**

- [ ] **Step 3: Sửa router**

```python
from app.database import get_db
from app.models import Attempt, Document, MasteryScore, Quiz, QuizItem, Topic, User
from app.routers.auth import get_current_user

router = APIRouter(prefix="/quiz", tags=["quiz"])


class GenerateQuizRequest(BaseModel):
    document_id: str | None = None
    document_ids: list[str] | None = None
    topic_name: str | None = None
    num_questions: int = 5
    difficulty: str | None = None
    generation_mode: str | None = None


@router.post("/generate")
def generate(
    req: GenerateQuizRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id
    requested_ids = req.document_ids or ([req.document_id] if req.document_id else [])
    if not requested_ids:
        raise HTTPException(400, "Cần cung cấp document_id hoặc document_ids.")
    if req.generation_mode is not None and req.generation_mode not in VALID_GENERATION_MODES:
        raise HTTPException(400, f"Chế độ sinh không hợp lệ. Chỉ nhận: {', '.join(VALID_GENERATION_MODES)}.")

    docs = (
        db.query(Document)
        .filter(Document.id.in_(requested_ids), Document.user_id == user_id, Document.status == "sẵn sàng")
        .all()
    )
    # ... (thân hàm còn lại giữ nguyên y hệt — mọi req.user_id trong thân hàm gốc
    #      đổi thành biến cục bộ `user_id` đã gán ở đầu hàm)


class SubmitAttemptRequest(BaseModel):
    quiz_item_id: str
    selected_answer: str


@router.post("/submit")
def submit_attempt(
    req: SubmitAttemptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id
    quiz_item = (
        db.query(QuizItem)
        .join(Quiz, QuizItem.quiz_id == Quiz.id)
        .filter(QuizItem.id == req.quiz_item_id, Quiz.user_id == user_id)
        .first()
    )
    # ... (thân hàm còn lại giữ nguyên, thay mọi req.user_id bằng user_id)
```

- [ ] **Step 4: Chạy test, xác nhận PASS.**

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/quiz.py tests/test_quiz_route.py
git commit -m "refactor: quiz.py dung Depends(get_current_user) thay user_id"
```

---

### Task 13: documents.py

**Files:**
- Modify: `backend/app/routers/documents.py`
- Test: `tests/test_documents_route.py` (sửa theo pattern Task 7, có thêm phần multipart upload).

- [ ] **Step 1: Sửa test theo pattern Task 7** — `upload_document` nhận `user_id` qua query param của multipart request (`client.post("/documents", params={"user_id": ...}, files=...)`); đổi thành override `get_current_user`, bỏ `user_id` khỏi `params`.

- [ ] **Step 2: Chạy test, xác nhận FAIL.**

- [ ] **Step 3: Sửa router**

```python
from app.database import SessionLocal, get_db
from app.models import Document, DocumentTopic, Topic, User
from app.routers.auth import get_current_user

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("")
async def upload_document(
    file: UploadFile,
    course_name: str | None = None,
    display_name: str | None = None,
    background_tasks: BackgroundTasks = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id
    if not file.filename:
        raise HTTPException(400, "Thiếu tên file.")
    # ... (thân hàm còn lại giữ nguyên y hệt dòng 178-250 bản gốc — đã dùng
    #      biến cục bộ `user_id`; XOÁ dòng `ensure_user(db, user_id)` ở dòng 233,
    #      user chắc chắn đã tồn tại vì đã đăng nhập qua get_current_user)

    background_tasks.add_task(
        _run_processing_job, document_id, storage_key, ext, file.filename, user_id
    )
    return {
        "document_id": document_id,
        "status": "đang xử lý",
        "version": version,
        "is_duplicate": is_duplicate,
    }


@router.get("")
def list_documents(
    include_old_versions: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Document).filter(Document.user_id == current_user.id)
    # ... (thân hàm còn lại giữ nguyên)


@router.get("/{document_id}/outline")
def get_document_outline(
    document_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    user_id = current_user.id
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == user_id).first()
    # ... (thân hàm còn lại giữ nguyên)


@router.get("/{document_id}/file")
def get_document_file(
    document_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    user_id = current_user.id
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == user_id).first()
    # ... (thân hàm còn lại giữ nguyên)


@router.delete("/{document_id}")
def delete_document(
    document_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    user_id = current_user.id
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == user_id).first()
    # ... (thân hàm còn lại giữ nguyên)
```

Lưu ý `_save_outline`/`_run_processing_job` (hàm nội bộ, không phải route) giữ nguyên chữ ký `user_id: str` — chúng chạy trong `BackgroundTasks`, không có request/cookie nào để đọc `current_user` ở đó; `user_id` truyền vào từ route (đã lấy từ `current_user.id`) trước khi tách sang thread nền, đúng như code gốc đã làm.

- [ ] **Step 4: Chạy test, xác nhận PASS.**

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/documents.py tests/test_documents_route.py
git commit -m "refactor: documents.py dung Depends(get_current_user) thay user_id"
```

---

### Task 14: context_assembly.py + chat.py (chưa có test cấp route — tạo mới)

**Files:**
- Modify: `backend/app/services/context_assembly.py:59-101`
- Modify: `backend/app/routers/chat.py`
- Create: `tests/test_chat_route.py`

**Interfaces:**
- `assemble_context` đổi chữ ký từ `assemble_context(db, req, needs_document_scope)` sang `assemble_context(db, req, needs_document_scope, user_id)` — tách khỏi việc đọc `req.user_id` trực tiếp, vì `AskRequest` sẽ không còn field đó.

- [ ] **Step 1: Viết test thất bại**

```python
# tests/test_chat_route.py
"""Integration test cho POST /chat/ask, GET /chat/conversations — trước đây
chỉ có test hành vi capability riêng lẻ (test_chat_study_plan_redirect.py),
chưa có test cấp route xác nhận Depends(get_current_user) hoạt động đúng và
cô lập đúng giữa 2 user."""
import os
import sys
import unittest
import uuid
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import Conversation, User
from app.routers.auth import get_current_user
from pg_test_helpers import fresh_test_session_factory


class ChatRouteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine, cls.SessionLocal = fresh_test_session_factory()

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        self.user_id = str(uuid.uuid4())
        self.other_user_id = str(uuid.uuid4())
        db = self.SessionLocal()
        try:
            db.add(User(id=self.user_id, email=f"{self.user_id}@test.local", password_hash="x", display_name="Hoa"))
            db.add(User(id=self.other_user_id, email=f"{self.other_user_id}@test.local", password_hash="x", display_name="Khac"))
            db.add(Conversation(id="convo-mine", user_id=self.user_id, course_name=None))
            db.add(Conversation(id="convo-other", user_id=self.other_user_id, course_name=None))
            db.commit()
        finally:
            db.close()

        self.current_user = User(
            id=self.user_id, email=f"{self.user_id}@test.local", password_hash="x", display_name="Hoa"
        )
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: self.current_user
        self.client = TestClient(app)
        self.addCleanup(app.dependency_overrides.clear)

    def test_list_conversations_only_returns_current_user_conversations(self):
        res = self.client.get("/chat/conversations")
        self.assertEqual(res.status_code, 200)
        ids = [c["id"] for c in res.json()]
        self.assertEqual(ids, ["convo-mine"])

    def test_get_conversation_of_other_user_returns_404(self):
        res = self.client.get("/chat/conversations/convo-other")
        self.assertEqual(res.status_code, 404)

    def test_ask_without_ready_documents_returns_400(self):
        res = self.client.post("/chat/ask", json={"question": "test?"})
        self.assertEqual(res.status_code, 400)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `JWT_SECRET_KEY=test DATABASE_URL=... TEST_DATABASE_URL=... python -m unittest tests.test_chat_route -v`
Expected: FAIL — route đòi `user_id` trong query/body.

- [ ] **Step 3: Sửa `context_assembly.py`**

Sửa `backend/app/services/context_assembly.py` dòng 59-101:
```python
def assemble_context(db: Session, req, needs_document_scope: bool, user_id: str) -> QAContext:
    """... (docstring giữ nguyên, chỉ thêm 1 dòng giải thích tham số user_id
    mới: lấy từ current_user.id ở router, không còn đọc req.user_id vì
    AskRequest không còn field đó sau khi chuyển sang Depends(get_current_user))."""
    ready_docs: List[Document] = []
    document_ids: Optional[Set[str]] = None

    if needs_document_scope:
        ready_docs = (
            db.query(Document)
            .filter(Document.user_id == user_id, Document.status == "sẵn sàng", Document.is_latest == True)
            .all()
        )
        if req.course_name:
            ready_docs = [d for d in ready_docs if d.course_name == req.course_name]

        if not ready_docs:
            raise HTTPException(400, "Chưa có tài liệu nào sẵn sàng để hỏi đáp.")

        document_ids = {d.id for d in ready_docs}

    conversation_id = req.conversation_id
    if not conversation_id:
        convo = Conversation(user_id=user_id, course_name=req.course_name)
        db.add(convo)
        db.commit()
        conversation_id = convo.id

    history = _load_conversation_history(db, conversation_id)

    return QAContext(
        document_ids=document_ids,
        ready_docs=ready_docs,
        conversation_id=conversation_id,
        history=history,
    )
```

Xoá `from app.database import ensure_user` (dòng 19) — không còn dùng.

- [ ] **Step 4: Sửa `chat.py`**

```python
from app.database import get_db
from app.models import (
    Attempt, Conversation, Document, DocumentTopic, MasteryScore,
    MemoryEvent, Message, QuizItem, Topic, User,
)
from app.routers.auth import get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])


class AskRequest(BaseModel):
    question: str
    course_name: str | None = None
    conversation_id: str | None = None
    top_k: int = 5
    min_score: float = 0.02
    level: str | None = None


@router.post("/ask")
def ask(
    req: AskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id
    if not req.question.strip():
        raise HTTPException(400, "Câu hỏi không được để trống.")

    capability = detect_capability(req.question)
    guardrail_result = None
    qa_result = None

    context = assemble_context(db, req, needs_document_scope=capability is None, user_id=user_id)
    ready_docs = context.ready_docs
    document_ids = context.document_ids
    conversation_id = context.conversation_id
    history = context.history

    if capability is not None:
        if capability.name == "study_plan":
            result = _build_study_plan_result(
                db, user_id, req.course_name, capability.params["days"], req.question,
                capability.params["multiple_days_mentioned"],
            )
        elif capability.name == "flashcard_due":
            result = _build_flashcard_due_result(db, user_id)
        else:
            result = _build_recommendation_result(db, user_id, req.course_name)
    else:
        llm_client = get_llm_client()
        guardrail_result = check_question(req.question, llm_client=llm_client)
        if guardrail_result.blocked:
            result = AnswerResult(answer=guardrail_result.message, is_grounded=False, sources=[])
        elif is_summarize_request(req.question):
            result = _build_summarize_result(db, user_id, req.question, ready_docs, llm_client)
        elif is_compare_request(req.question):
            result = _build_compare_result(db, user_id, req.question, document_ids, llm_client)
        elif is_apply_request(req.question):
            result = build_apply_result(db, user_id, document_ids, req.question, llm_client)
        else:
            learner = build_learner_context(db, user_id, requested_level=req.level, query=req.question)
            effective_top_k = req.top_k + LEVEL_TOP_K_BOOST if learner.effective_level else req.top_k

            def _retrieve(query: str, top_k: int, mode: str):
                return retrieve_chunks(
                    db=db, user_id=user_id, query=query, top_k=top_k,
                    document_ids=document_ids, mode=mode,
                )

            retrieval_query = build_retrieval_query(req.question, history)

            if has_unresolved_reference(req.question, history):
                result = AnswerResult(
                    answer=NEEDS_CLARIFICATION_MESSAGE, is_grounded=False, sources=[],
                    needs_clarification=True,
                )
            else:
                def _suggest_topics(question: str) -> list[str]:
                    rows = (
                        db.query(DocumentTopic)
                        .filter(DocumentTopic.user_id == user_id, DocumentTopic.document_id.in_(document_ids))
                        .all()
                    )
                    plausible_titles = set(filter_topic_titles([r.title for r in rows]))
                    rows = [r for r in rows if r.title in plausible_titles]
                    if not rows:
                        return []
                    question_words = _content_words(question)
                    scored = sorted(
                        rows, key=lambda r: len(_content_words(r.title) & question_words), reverse=True
                    )
                    return [r.title for r in scored[:MAX_SUGGESTED_TOPICS]]

                qa_result = answer_with_fallback(
                    question=req.question, retrieval_query=retrieval_query, llm_client=llm_client,
                    retrieve_fn=_retrieve, suggest_topics_fn=_suggest_topics,
                    searched_documents=[{"id": d.id, "file_name": d.file_name} for d in ready_docs],
                    top_k=effective_top_k, min_score=req.min_score, conversation_history=history,
                    level=learner.effective_level, learning_goal=learner.learning_goal,
                    recalled_events=learner.recalled_events,
                )
                result = AnswerResult(answer=qa_result.answer, is_grounded=qa_result.is_grounded, sources=qa_result.sources)

    db.add(Message(conversation_id=conversation_id, role="user", content=req.question))
    db.add(Message(
        conversation_id=conversation_id, role="assistant", content=result.answer,
        is_grounded=result.is_grounded,
        cited_sources=json.dumps([
            {
                "document_name": s.document_name, "position_ref": s.position_ref,
                "chunk_id": s.chunk_id, "document_id": s.document_id, "text": s.text,
                "supporting_sentences": supporting_sentences(result.answer, s.text),
            }
            for s in result.sources
        ], ensure_ascii=False),
    ))

    if capability is None and guardrail_result is not None and not guardrail_result.blocked:
        event_type, content = _classify_question_event(req.question, result)
        record_event(db, user_id=user_id, event_type=event_type, content=content)

    db.commit()

    return {
        "conversation_id": conversation_id,
        "answer": result.answer,
        "is_grounded": result.is_grounded,
        "abstained": qa_result.abstained if qa_result else False,
        "needs_clarification": (qa_result.needs_clarification if qa_result else False) or result.needs_clarification,
        "injection_flag": qa_result.injection_flag if qa_result else False,
        "partial": qa_result.partial if qa_result else False,
        "sources": [
            {
                "document_name": s.document_name, "position_ref": s.position_ref,
                "chunk_id": s.chunk_id, "document_id": s.document_id, "text": s.text,
                "supporting_sentences": supporting_sentences(result.answer, s.text),
            }
            for s in result.sources
        ],
        "search_report": (
            {
                "passes_run": qa_result.search_report.passes_run,
                "searched_documents": qa_result.search_report.searched_documents,
                "near_misses": [
                    {
                        "chunk_id": n.chunk_id, "document_id": n.document_id,
                        "document_name": n.document_name, "position_ref": n.position_ref,
                        "text": n.text, "score": n.score,
                    }
                    for n in qa_result.search_report.near_misses
                ],
                "suggested_topics": qa_result.search_report.suggested_topics,
            }
            if qa_result and qa_result.search_report else None
        ),
    }


@router.get("/conversations")
def list_conversations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conversations = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.created_at.desc())
        .all()
    )
    # ... (thân hàm còn lại giữ nguyên)


@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    convo = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == current_user.id)
        .first()
    )
    # ... (thân hàm còn lại giữ nguyên)
```

(Các hàm helper `_build_recommendation_result`, `_build_study_plan_result`, `_build_flashcard_due_result`, `_build_summarize_result`, `_build_compare_result` đã nhận `user_id: str` làm tham số từ trước — KHÔNG cần sửa chữ ký, chỉ caller trong `ask()` đổi từ `req.user_id` sang biến `user_id` cục bộ.)

- [ ] **Step 5: Chạy test, xác nhận PASS**

Run lệnh Step 2 lại. Expected: PASS (3/3).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/context_assembly.py backend/app/routers/chat.py tests/test_chat_route.py
git commit -m "refactor: chat.py va context_assembly.py dung Depends(get_current_user) thay user_id"
```

---

### Task 15: Dọn `ensure_user` + regression cô lập giữa 2 user

**Files:**
- Modify: `backend/app/database.py:41-64`
- Test: `tests/test_cross_user_isolation.py` (mới)

**Interfaces:**
- Consumes: mọi router đã migrate ở Task 7-14.

- [ ] **Step 1: Xác nhận không còn nơi nào gọi `ensure_user`**

Run: `grep -rn "ensure_user" backend/app` — Expected: chỉ còn định nghĩa hàm trong `database.py`, không còn lời gọi nào ở `routers/`.

- [ ] **Step 2: Xoá hàm `ensure_user`**

Xoá toàn bộ hàm `ensure_user` (dòng 41-64) khỏi `backend/app/database.py` — không còn ai gọi (mọi user giờ được tạo qua `POST /auth/register`, chắc chắn tồn tại trước khi `get_current_user` cho phép request đi tiếp).

- [ ] **Step 3: Viết test regression cô lập giữa 2 user**

```python
# tests/test_cross_user_isolation.py
"""Regression Phase 3 — user A không được đọc/sửa/xoá resource của user B dù
biết ID, kể cả sau khi mọi router đã đổi sang Depends(get_current_user)."""
import os
import sys
import unittest
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import Document, User
from app.routers.auth import get_current_user
from pg_test_helpers import fresh_test_session_factory


class CrossUserIsolationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine, cls.SessionLocal = fresh_test_session_factory()

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        self.owner_id = str(uuid.uuid4())
        self.attacker_id = str(uuid.uuid4())
        db = self.SessionLocal()
        try:
            db.add(User(id=self.owner_id, email=f"{self.owner_id}@test.local", password_hash="x", display_name="Chủ"))
            db.add(User(id=self.attacker_id, email=f"{self.attacker_id}@test.local", password_hash="x", display_name="Kẻ khác"))
            db.flush()
            self.doc_id = str(uuid.uuid4())
            db.add(Document(id=self.doc_id, user_id=self.owner_id, file_name="bimat.pdf", status="sẵn sàng"))
            db.commit()
        finally:
            db.close()

        self.attacker = User(
            id=self.attacker_id, email=f"{self.attacker_id}@test.local", password_hash="x", display_name="Kẻ khác"
        )
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: self.attacker
        self.client = TestClient(app)
        self.addCleanup(app.dependency_overrides.clear)

    def test_attacker_cannot_see_owners_document_in_list(self):
        res = self.client.get("/documents")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), [])

    def test_attacker_cannot_fetch_owners_document_outline_by_id(self):
        res = self.client.get(f"/documents/{self.doc_id}/outline")
        self.assertEqual(res.status_code, 404)

    def test_attacker_cannot_delete_owners_document_by_id(self):
        res = self.client.delete(f"/documents/{self.doc_id}")
        self.assertEqual(res.status_code, 404)

        db = self.SessionLocal()
        try:
            self.assertIsNotNone(db.query(Document).filter(Document.id == self.doc_id).first())
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 4: Chạy toàn bộ suite, xác nhận PASS**

Run: `JWT_SECRET_KEY=test DATABASE_URL=... TEST_DATABASE_URL=... python -m unittest discover -s tests -v`
Expected: PASS toàn bộ, không có `ImportError` nào do `ensure_user` bị xoá.

- [ ] **Step 5: Commit**

```bash
git add backend/app/database.py tests/test_cross_user_isolation.py
git commit -m "refactor: xoa ensure_user (khong con dung), them regression co lap user"
```

Phase 3 hoàn tất — acceptance criteria mục 9-10 của `docs/auth-spec.md` đã có test bao phủ.

---

## PHASE 4 — Frontend

### Task 16: api.js — credentials + auth endpoints

**Files:**
- Modify: `frontend/src/api.js` (toàn bộ file — xoá `CURRENT_USER_ID`, thêm `credentials: "include"` vào mọi `fetch`, xoá `user_id` khỏi mọi params/body, thêm 4 hàm auth).

**Interfaces:**
- Produces: `register(email, password, displayName)`, `login(email, password)`, `logout()`, `getCurrentUser()` — Task 17 (AuthContext) dùng các hàm này.

- [ ] **Step 1: Sửa `frontend/src/api.js`**

Xoá dòng 4-5 (`// user_id tạm thời...` và `export const CURRENT_USER_ID = "demo-user";`).

Thêm vào sau `raiseFriendlyError` (sau dòng 24):
```javascript
export async function register(email, password, displayName) {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, display_name: displayName }),
  });
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}

export async function login(email, password) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}

export async function logout() {
  const res = await fetch(`${API_BASE}/auth/logout`, { method: "POST", credentials: "include" });
  if (!res.ok) await raiseFriendlyError(res);
}

export async function getCurrentUser() {
  const res = await fetch(`${API_BASE}/auth/me`, { credentials: "include" });
  if (!res.ok) await raiseFriendlyError(res);
  return res.json();
}
```

Với **mọi** hàm còn lại trong file (`uploadDocument`, `listDocuments`, `deleteDocument`, `generateQuiz`, `submitAttempt`, `getMastery`, `getMistakes`, `askQuestion`, `listConversations`, `getConversation`, `getDocumentOutline`, `generateFlashcards`, `saveFlashcardFromAnswer`, `listDueFlashcards`, `getFlashcardBoard`, `getFlashcardMistakes`, `getFlashcardHistory`, `reviewFlashcard`, `listCourses`, `setCourseExamDate`, `deleteCourseExamDate`, `getStudyPlan`, `markTopicReviewed`, `getProfile`, `updateProfile`, `resetProfile`, `documentFileUrl`):
1. Thêm `credentials: "include"` vào object thứ 2 của mọi `fetch(...)` (kể cả các lời gọi `fetch(url)` không có object thứ 2 hiện tại — vd `listDocuments`, `getMastery` — phải thêm `fetch(url, { credentials: "include" })`).
2. Xoá `user_id: CURRENT_USER_ID` khỏi mọi `URLSearchParams({...})` và mọi `JSON.stringify({...})`.
3. `documentFileUrl` (dòng 311-315): bỏ `?user_id=${CURRENT_USER_ID}` khỏi URL — ảnh mở trực tiếp qua `<a href>`/`<img src>` (không phải `fetch`) nên không tự gửi cookie qua `credentials`; endpoint `/documents/{id}/file` giờ cần cookie nhưng thẻ `<img>`/link trình duyệt tự đính kèm cookie same-origin/cross-site theo `SameSite` đã cấu hình — không cần sửa gì thêm ở hàm này ngoài bỏ query param.

- [ ] **Step 2: Xác nhận build frontend không lỗi**

Run: `cd frontend && npm run build`
Expected: build thành công, không còn tham chiếu `CURRENT_USER_ID` nào (grep `grep -rn CURRENT_USER_ID frontend/src` phải rỗng).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api.js
git commit -m "refactor: api.js gui cookie qua credentials include, bo CURRENT_USER_ID"
```

---

### Task 17: AuthContext

**Files:**
- Create: `frontend/src/contexts/AuthContext.jsx`

**Interfaces:**
- Consumes: `login`, `register`, `logout`, `getCurrentUser` từ `frontend/src/api.js` (Task 16).
- Produces: `AuthProvider` component, `useAuth()` hook trả `{ user, status, login, register, logout }` với `status` ∈ `"unknown" | "authenticated" | "unauthenticated"` — Task 18-20 dùng hook này.

- [ ] **Step 1: Viết implementation**

```javascript
// frontend/src/contexts/AuthContext.jsx
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import * as api from "../api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  // "unknown" tránh nhấp nháy màn Login lúc F5 trong khi GET /auth/me
  // chưa trả lời — xem docs/auth-spec.md mục 11.
  const [status, setStatus] = useState("unknown");

  useEffect(() => {
    api
      .getCurrentUser()
      .then((u) => {
        setUser(u);
        setStatus("authenticated");
      })
      .catch(() => {
        setUser(null);
        setStatus("unauthenticated");
      });
  }, []);

  const login = useCallback(async (email, password) => {
    const u = await api.login(email, password);
    setUser(u);
    setStatus("authenticated");
    return u;
  }, []);

  const register = useCallback(async (email, password, displayName) => {
    const u = await api.register(email, password, displayName);
    setUser(u);
    setStatus("authenticated");
    return u;
  }, []);

  const logout = useCallback(async () => {
    await api.logout();
    setUser(null);
    setStatus("unauthenticated");
  }, []);

  return (
    <AuthContext.Provider value={{ user, status, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth phải được gọi bên trong AuthProvider");
  return ctx;
}
```

- [ ] **Step 2: Verify thủ công (chưa gắn vào App — Task 20 mới wiring)**

Run: `cd frontend && npm run build` — Expected: build thành công, không lỗi cú pháp JSX.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/contexts/AuthContext.jsx
git commit -m "feat: them AuthContext quan ly trang thai dang nhap"
```

---

### Task 18: LoginPage + RegisterPage

**Files:**
- Create: `frontend/src/pages/LoginPage.jsx`, `frontend/src/pages/RegisterPage.jsx`

**Interfaces:**
- Consumes: `useAuth()` (Task 17), `Button`/`Input`/`Card` từ `frontend/src/components/ui/` (quy ước UI có sẵn).

- [ ] **Step 1: Viết `LoginPage.jsx`**

```jsx
// frontend/src/pages/LoginPage.jsx
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import Input from "../components/ui/Input";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <Card className="w-full max-w-sm p-6">
        <h1 className="mb-4 text-xl font-semibold text-foreground">Đăng nhập EduTutor</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <Input
            type="password"
            placeholder="Mật khẩu"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? "Đang đăng nhập..." : "Đăng nhập"}
          </Button>
        </form>
        <p className="mt-4 text-sm text-muted-foreground">
          Chưa có tài khoản?{" "}
          <Link to="/register" className="text-primary hover:underline">
            Đăng ký
          </Link>
        </p>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Viết `RegisterPage.jsx`**

```jsx
// frontend/src/pages/RegisterPage.jsx
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import Input from "../components/ui/Input";

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register(email, password, displayName);
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <Card className="w-full max-w-sm p-6">
        <h1 className="mb-4 text-xl font-semibold text-foreground">Tạo tài khoản EduTutor</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            placeholder="Tên hiển thị"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            required
          />
          <Input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <Input
            type="password"
            placeholder="Mật khẩu (8-64 ký tự)"
            minLength={8}
            maxLength={64}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? "Đang tạo tài khoản..." : "Đăng ký"}
          </Button>
        </form>
        <p className="mt-4 text-sm text-muted-foreground">
          Đã có tài khoản?{" "}
          <Link to="/login" className="text-primary hover:underline">
            Đăng nhập
          </Link>
        </p>
      </Card>
    </div>
  );
}
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build` — Expected: build thành công.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/LoginPage.jsx frontend/src/pages/RegisterPage.jsx
git commit -m "feat: them LoginPage va RegisterPage"
```

---

### Task 19: ProtectedRoute + wiring App.jsx/main.jsx

**Files:**
- Create: `frontend/src/components/ProtectedRoute.jsx`
- Modify: `frontend/src/main.jsx`, `frontend/src/App.jsx`

**Interfaces:**
- Consumes: `useAuth()` (Task 17), `LoginPage`/`RegisterPage` (Task 18).

- [ ] **Step 1: Viết `ProtectedRoute.jsx`**

```jsx
// frontend/src/components/ProtectedRoute.jsx
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

// "unknown" chưa render gì (tránh nhấp nháy Login lúc F5 trước khi GET
// /auth/me trả lời — docs/auth-spec.md mục 11), KHÔNG coi là chưa đăng nhập.
export default function ProtectedRoute() {
  const { status } = useAuth();

  if (status === "unknown") return null;
  if (status === "unauthenticated") return <Navigate to="/login" replace />;
  return <Outlet />;
}
```

- [ ] **Step 2: Sửa `frontend/src/main.jsx`**

```jsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { AuthProvider } from "./contexts/AuthContext";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </React.StrictMode>
);
```

- [ ] **Step 3: Sửa `frontend/src/App.jsx`**

```jsx
import { BrowserRouter, Route, Routes, Outlet, useLocation } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import ErrorBoundary from "./components/ErrorBoundary";
import ProtectedRoute from "./components/ProtectedRoute";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import DashboardPage from "./pages/DashboardPage";
import UploadPage from "./pages/UploadPage";
import ChatPage from "./pages/ChatPage";
import QuizPage from "./pages/QuizPage";
import FlashcardsPage from "./pages/FlashcardsPage";
import StudyPlanPage from "./pages/StudyPlanPage";
import ProfilePage from "./pages/ProfilePage";

const PAGE_TITLES = {
  "/": "Tổng quan",
  "/documents": "Tài liệu học tập",
  "/chat": "Hỏi đáp tài liệu",
  "/quiz": "Quiz tự kiểm tra",
  "/flashcards": "Flashcard ôn tập",
  "/study-plan": "Kế hoạch ôn tập",
  "/profile": "Hồ sơ học tập",
};

function Layout() {
  const location = useLocation();
  const title = PAGE_TITLES[location.pathname] || "EduTutor";
  return (
    <AppShell title={title}>
      <ErrorBoundary key={location.pathname}>
        <Outlet />
      </ErrorBoundary>
    </AppShell>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/documents" element={<UploadPage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/quiz" element={<QuizPage />} />
            <Route path="/flashcards" element={<FlashcardsPage />} />
            <Route path="/study-plan" element={<StudyPlanPage />} />
            <Route path="/profile" element={<ProfilePage />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
```

- [ ] **Step 4: Verify thủ công end-to-end**

Chạy backend (`uvicorn app.main:app --reload`, với `JWT_SECRET_KEY` đã set) và frontend (`npm run dev`):
1. Mở `http://localhost:5173/` chưa đăng nhập → phải tự chuyển tới `/login` (không nhấp nháy).
2. Đăng ký tài khoản mới ở `/register` → phải chuyển vào `/` (Dashboard) ngay, không cần đăng nhập lại.
3. F5 lại trang `/` → vẫn ở `/` (không bị đá về `/login`), xác nhận cookie + `/auth/me` hoạt động.
4. Vào `/profile` (Task 20 sẽ thêm nút logout) hoặc gọi `POST http://localhost:8001/auth/logout` bằng tay → F5 lại `/` → phải bị chuyển về `/login`.

Expected: cả 4 bước đúng như mô tả.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ProtectedRoute.jsx frontend/src/main.jsx frontend/src/App.jsx
git commit -m "feat: wiring ProtectedRoute, /login, /register vao App"
```

---

### Task 20: Nút đăng xuất ở Topbar

**Files:**
- Modify: `frontend/src/components/layout/Topbar.jsx`

**Interfaces:**
- Consumes: `useAuth()` (Task 17).

- [ ] **Step 1: Sửa `Topbar.jsx`**

Thêm import và nút logout cạnh icon Profile hiện có (dòng 1-6, 28-39) — theo đúng quy ước đã thiết lập trong dự án: mục liên quan tài khoản đặt ở góc topbar, không trộn vào sidebar chính:
```jsx
import { LogOut, Menu, Moon, Sun, UserCog } from "lucide-react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { useDarkMode } from "../../hooks/useDarkMode";
import { cn } from "../../lib/cn";

export default function Topbar({ title, onMenuClick }) {
  const { isDark, toggle } = useDarkMode();
  const { logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/login");
  }

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-border bg-card/80 px-4 backdrop-blur sm:px-6">
      <button
        type="button"
        onClick={onMenuClick}
        className="rounded-md p-2 text-muted-foreground hover:bg-muted cursor-pointer lg:hidden"
        aria-label="Mở menu điều hướng"
      >
        <Menu className="h-5 w-5" />
      </button>
      <h1 className="flex-1 truncate text-lg font-semibold text-foreground">{title}</h1>
      <button
        type="button"
        onClick={toggle}
        className="flex h-11 w-11 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label={isDark ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối"}
      >
        {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
      </button>
      <NavLink
        to="/profile"
        className={({ isActive }) =>
          cn(
            "flex h-11 w-11 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            isActive && "bg-primary/10 text-primary"
          )
        }
        aria-label="Hồ sơ học tập"
      >
        <UserCog className="h-5 w-5" />
      </NavLink>
      <button
        type="button"
        onClick={handleLogout}
        className="flex h-11 w-11 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label="Đăng xuất"
      >
        <LogOut className="h-5 w-5" />
      </button>
    </header>
  );
}
```

- [ ] **Step 2: Verify thủ công**

Trong phiên đang đăng nhập (từ Task 19 Step 4), bấm icon đăng xuất mới ở Topbar → phải chuyển ngay về `/login`; F5 lại `/` → phải vẫn ở `/login` (cookie đã bị xoá).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/layout/Topbar.jsx
git commit -m "feat: them nut dang xuat vao Topbar"
```

Phase 4 hoàn tất — acceptance criteria mục 11 của `docs/auth-spec.md` (auth state machine, không nhấp nháy Login lúc F5) đã verify thủ công.

---

## PHASE 5 — Integration / Regression

### Task 21: Chạy toàn bộ regression + cập nhật README

**Files:**
- Modify: `README.md` (mục "Chạy test" — thêm `JWT_SECRET_KEY` vào lệnh mẫu; mục biến môi trường — thêm `JWT_SECRET_KEY`/`JWT_EXPIRE_MINUTES`).

- [ ] **Step 1: Chạy toàn bộ test suite backend**

Run:
```
JWT_SECRET_KEY=test-secret-key-do-not-use-in-prod \
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/edututor_test \
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/edututor_test \
python -m unittest discover -s tests -v
```
Expected: PASS toàn bộ (test cũ + test mới thêm ở Phase 1-3), không có test nào còn tham chiếu `user_id` như tham số request.

- [ ] **Step 2: Grep xác nhận không còn `user_id` client-controlled nào sót lại**

Run: `grep -rn "user_id: str" backend/app/routers/` — Expected: 0 kết quả trong path params/query/body của route handler (chỉ còn `user_id` như tên biến cục bộ `user_id = current_user.id`, hoặc tham số của hàm nội bộ không phải route như `_save_outline`/`_run_processing_job`/`_topics_reviewed_today`).

- [ ] **Step 3: Regression thủ công toàn bộ luồng chính** (đã có `npm run dev` + backend chạy từ Task 19):

- [ ] Đăng ký → upload tài liệu → hỏi đáp `/chat` → sinh quiz → làm quiz → sinh flashcard → ôn flashcard → xem mastery/kế hoạch ôn/hồ sơ — mỗi bước không còn route nào trả 401/422 do thiếu `user_id`.
- [ ] Mở 2 trình duyệt (hoặc 1 trình duyệt thường + 1 ẩn danh), đăng ký 2 tài khoản khác nhau, xác nhận tài liệu/quiz/flashcard của tài khoản A không hiện ra ở tài khoản B.

- [ ] **Step 4: Cập nhật README**

Sửa mục "Chạy test" trong `README.md` (dòng lệnh có `DATABASE_URL=...TEST_DATABASE_URL=...python -m unittest discover -s tests -v`) — thêm `JWT_SECRET_KEY=test-secret-key-do-not-use-in-prod` vào đầu dòng lệnh mẫu.

Thêm vào mục liệt kê biến môi trường bắt buộc (gần dòng nói về `DATABASE_URL`, `OPENAI_API_KEY`...): `JWT_SECRET_KEY` (bắt buộc — xem `.env.example`).

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: cap nhat README voi bien moi truong JWT_SECRET_KEY"
```

Phase 5 hoàn tất — toàn bộ acceptance criteria (`docs/auth-spec.md` mục 12) đã verify bằng test tự động (backend) + thao tác tay (frontend, vì chưa có test framework JS trong repo).
