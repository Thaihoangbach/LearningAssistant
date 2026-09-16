# Authentication Spec v1 — EduTutor

Spec cho tính năng đăng nhập thật (F11 trong PRD, hiện đang "chưa có" — mọi request dùng `user_id="demo-user"` cố định). Tài liệu này là nguồn tham chiếu cho implementation plan — mọi task trong plan phải trace được về một mục ở đây.

## 1. Bối cảnh & quyết định đã chốt

- Cơ chế: email + mật khẩu (không OAuth, không 2FA).
- Session: JWT trong cookie `HttpOnly`.
- Dữ liệu `demo-user` hiện có: **bỏ, không migrate** — xem mục 9 (migration) để biết hệ quả kỹ thuật cụ thể.
- MVP chỉ có Register / Login / Logout, cộng `GET /auth/me` làm nền (không phải feature hiển thị, frontend cần nó để khôi phục session sau F5).
- Chuyển toàn bộ router hiện có (`documents`, `chat`, `quiz`, `flashcard`, `mastery`, `study_plan`, `profile`, `courses`) từ nhận `user_id` do client tự gửi sang `Depends(get_current_user)` — không giữ đường lùi. Việc này thuộc Phase 3 của implementation plan, spec này chỉ định nghĩa `get_current_user` (mục 6).

**Ngoài phạm vi MVP:** forgot/reset password, xác thực email, đổi mật khẩu, xoá tài khoản, refresh token, role/permission, rate limiting theo IP.

## 2. Data model

```python
class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)   # MỚI
    display_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
```

Không thêm `is_active`/`is_verified`/`deleted_at` — chưa có use case nào cần (không có admin disable account, không có email verification trong MVP). Thêm field "để sau này dùng" là đoán trước yêu cầu chưa tồn tại — không làm.

## 3. Password policy

- Độ dài: **8–64 ký tự**. Đây là policy sản phẩm, KHÔNG phải giới hạn kỹ thuật của bcrypt (72 byte UTF-8, khác 72 ký tự — một mật khẩu tiếng Việt có dấu có thể vượt 72 byte trước khi chạm 64 ký tự). Không validate byte-length riêng cho MVP; 64 ký tự đã an toàn dưới ngưỡng bcrypt cho hầu hết trường hợp thực tế.
- Không ép độ phức tạp (chữ hoa/số/ký tự đặc biệt).
- Hash bằng `bcrypt` (thêm dependency `bcrypt`). Không dùng Argon2id cho MVP — bcrypt vẫn được OWASP chấp nhận, và đổi thuật toán sau này chỉ sửa 1 file vì logic được cô lập (xem dưới).
- Không gọi `bcrypt.hashpw`/`bcrypt.checkpw` trực tiếp từ router. Đặt 2 hàm thường (không cần class/interface — chỉ có 1 implementation) trong `app/services/auth_service.py`, theo đúng quy ước đã có của codebase (`app/services/document_cleanup.py`, `app/services/learner_context.py`):

```python
def hash_password(password: str) -> str: ...
def verify_password(password: str, password_hash: str) -> bool: ...
```

- Email: chuẩn hoá `email.strip().lower()` trước khi lookup hoặc lưu — thực hiện ở tầng service, không phải ở router hay Pydantic schema.

## 4. JWT

- Thư viện: `PyJWT`. Thuật toán: HS256.
- Claims — **tối giản, không có `email`** (tránh stale claim nếu email đổi sau này; identity chỉ cần `sub`, tra `User.email` từ DB khi cần):

```json
{
  "sub": "<user_id>",
  "iat": 1758010000,
  "exp": 1758614800
}
```

- Secret: env `JWT_SECRET_KEY`, bắt buộc — fail-fast khi thiếu, cùng pattern với `DATABASE_URL` trong `app/database.py`.
- Hết hạn: mặc định 7 ngày (10080 phút), chỉnh qua env `JWT_EXPIRE_MINUTES`.

**Hệ quả cần ghi nhận (không phải bug, là giới hạn đã biết của MVP):** MVP không có cơ chế revoke token phía server. `POST /auth/logout` chỉ xoá cookie ở trình duyệt hiện tại (`Set-Cookie` với `max_age=0`) — nó **không** làm JWT hết hiệu lực về mặt mật mã học. Nếu một JWT đã bị copy ra ngoài trước khi logout (vd bị đánh cắp qua XSS ở nơi khác, hoặc lưu thủ công), nó vẫn dùng được cho tới khi hết hạn tự nhiên (`exp`), bất kể user đã "logout". Chấp nhận được cho MVP (app học tập cá nhân, không phải hệ thống tài chính); nếu cần revoke thật, phải thêm bảng blacklist/token version — nằm ngoài phạm vi MVP.

## 5. Cookie & CORS

**Cookie:**
- Tên: `access_token`, `httpOnly=True`, `path="/"`, `max_age` = giây tương ứng `JWT_EXPIRE_MINUTES`.
- `Secure`/`SameSite` suy ra từ `FRONTEND_URL` có được set hay không (đã có sẵn convention này trong `compute_allowed_origins()` ở `main.py` cho CORS — dùng lại đúng tín hiệu đó, không thêm biến env mới cho MVP), nhưng **đóng gói thành 1 hàm thuần, không rải logic if/else trong router**:

```python
def get_cookie_settings(frontend_url: str | None) -> dict:
    """frontend_url có giá trị -> prod, cross-site (frontend/backend khác domain)
    -> cần Secure=True, SameSite="none" để trình duyệt còn gửi cookie.
    Không có -> dev, cả hai đều localhost (cùng site, khác port) -> SameSite="lax" đã đủ,
    Secure=False vì dev chạy http."""
    if frontend_url:
        return {"secure": True, "samesite": "none"}
    return {"secure": False, "samesite": "lax"}
```

Đặt cạnh `compute_allowed_origins()` trong `main.py` (cùng chỗ, cùng lý do tồn tại) hoặc trong `auth_service.py` — quyết định lúc viết plan, không ảnh hưởng spec.

**CORS:** `main.py` đã cấu hình đúng từ trước — `allow_credentials=True` + origin cụ thể (không wildcard). Không cần đổi gì ở backend. Việc còn thiếu là **frontend phải thêm `credentials: "include"` vào mọi lời gọi `fetch`** trong `frontend/src/api.js` — nếu thiếu, cookie sẽ không được gửi kèm request và mọi endpoint auth-required trả 401 dù đã login. Đây là điều kiện bắt buộc của Phase 4, ghi rõ ở đây để không phát hiện muộn lúc deploy.

## 6. `get_current_user` dependency

```python
def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Đọc cookie access_token, decode JWT, load User theo sub.
    Raise HTTPException(401, "Chưa đăng nhập") nếu: thiếu cookie, JWT invalid/expired,
    hoặc user_id trong sub không còn tồn tại trong DB."""
```

Mọi route hiện đang nhận `user_id: str` từ query/body (8 router, xem Phase 3 của plan) sẽ đổi sang `current_user: User = Depends(get_current_user)` và dùng `current_user.id` thay cho `req.user_id`/`user_id` param.

## 7. API contracts

| Method | Endpoint | Auth | Input | Thành công | Lỗi |
|---|---|---|---|---|---|
| POST | `/auth/register` | ❌ | `{email, password, display_name}` | 201 + `UserOut` + `Set-Cookie` | 409 email đã tồn tại; 422 validation |
| POST | `/auth/login` | ❌ | `{email, password}` | 200 + `UserOut` + `Set-Cookie` | 401 generic |
| POST | `/auth/logout` | ✅ | — | 204 + clear cookie | 401 nếu chưa đăng nhập |
| GET | `/auth/me` | ✅ | — | 200 + `UserOut` | 401 nếu chưa đăng nhập |

```python
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=64)
    display_name: str = Field(min_length=1, max_length=100)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    created_at: datetime
```

`UserOut` không bao giờ chứa `password_hash`. Register set cookie ngay (auto-login) — frontend không cần gọi `/login` thêm sau khi đăng ký thành công.

**Race condition trên email trùng:** KHÔNG dùng pattern "check tồn tại rồi mới insert" (`if user_exists(email): raise 409` rồi mới `db.add(User(...))`) — hai request đồng thời cùng email đều có thể pass qua bước check trước khi request nào commit xong (TOCTOU). Insert trước, bắt `IntegrityError` (vi phạm `unique` constraint ở DB) rồi map sang `409` — DB constraint là nguồn xác thực cuối cùng, không phải một query kiểm tra trước đó.

## 8. Error contract

- Tất cả lỗi trả `{"detail": "<message tiếng Việt, thân thiện>"}`, khớp `raiseFriendlyError()` đã có trong `frontend/src/api.js`.
- Login sai (email không tồn tại HOẶC sai mật khẩu) → **cùng một message**: `"Email hoặc mật khẩu không đúng"` — không phân biệt 2 trường hợp, tránh lộ email nào đã đăng ký qua endpoint login.
- Register với email đã tồn tại → `409 {"detail": "Email đã được đăng ký"}`. Ghi nhận: điều này TỰ NÓ đã là 1 side-channel cho phép dò email tồn tại qua `/register` (khác với `/login` không lộ) — chấp nhận được cho MVP (app học tập cá nhân, không phải mục tiêu giá trị cao), không coi là blocker.
- `/auth/me`, `/auth/logout` thiếu/hết hạn/sai cookie → `401 {"detail": "Chưa đăng nhập"}`.

## 9. Migration (Alembic) — hệ quả kỹ thuật của việc bỏ dữ liệu demo-user

Đã verify: cả 13 cột `user_id = Column(String, ForeignKey("users.id"), ...)` trong `app/models.py` đều **không** khai báo `ondelete=` — không có `ON DELETE CASCADE` ở tầng DB, và SQLAlchemy `relationship()` không tự tạo cascade DB-level (cascade của ORM chỉ áp dụng khi xoá qua session, không áp dụng cho raw SQL trong migration). Vì vậy xoá bảng `users` bằng `DELETE`/`DROP` thường sẽ dính `ForeignKeyViolation` nếu còn hàng tham chiếu.

Migration thêm cột `password_hash NOT NULL` sẽ dùng thẳng:

```python
op.execute("TRUNCATE TABLE users CASCADE")
op.add_column("users", sa.Column("password_hash", sa.String(), nullable=False))
```

`TRUNCATE ... CASCADE` của Postgres tự dọn mọi bảng có FK trỏ tới `users` bất kể `ondelete` có khai báo hay không — đây là cách xử lý đúng, không phải phỏng đoán cascade sẽ "tự chạy" qua ORM. Migration này **phá huỷ toàn bộ dữ liệu hiện có** (users, documents, conversations, quiz, flashcard, mastery, memory...) — đúng theo quyết định đã duyệt ("bỏ demo-user, không migrate"), nhưng **phải dừng lại xin xác nhận trước khi chạy migration này trên bất kỳ DB đã deploy/có dữ liệu thật** (không chạy tự động trong CI/CD mà không có bước duyệt), vì đây là hành động phá huỷ không thể hoàn tác trên state chung.

## 10. Threat model

- **CSRF:** JWT nằm trong cookie `HttpOnly` → trình duyệt tự gửi cookie kèm mọi request cùng site/cross-site (tuỳ `SameSite`), kể cả từ site khác nếu `SameSite=none` (bắt buộc ở production vì frontend/backend khác domain). `HttpOnly` chỉ chống JavaScript đọc cookie, KHÔNG chống CSRF.
  Mitigation thực tế đã có trong kiến trúc này (không cần thêm CSRF token cho MVP): mọi endpoint đổi state của EduTutor bắt buộc `Content-Type: application/json` (xem toàn bộ POST/PUT trong `frontend/src/api.js`) — "simple request" theo spec CORS chỉ cho phép `application/x-www-form-urlencoded`/`multipart/form-data`/`text/plain` mà không cần preflight, nên một form CSRF cổ điển từ site lạ không thể tạo ra JSON hợp lệ mà Pydantic chấp nhận; còn `fetch` JS cố giả JSON sẽ bị chặn ở bước CORS preflight vì `ALLOWED_ORIGINS` chỉ whitelist đúng 1 domain frontend, không wildcard. **Điều kiện để mitigation này còn hiệu lực** (phải giữ khi implement Phase 3+): không thêm origin `*` vào CORS, không có endpoint mutating nào chấp nhận `GET` hoặc `form-urlencoded` để đổi state.
- **Token theft:** xem mục 4 (JWT không revoke được tới khi hết hạn tự nhiên).
- **Email enumeration:** xem mục 8 (chấp nhận lộ qua `/register`, không lộ qua `/login`).
- **Password ở log:** không log request body của `/auth/register`, `/auth/login` (kể cả ở mức lỗi/exception handler chung của `main.py`) — cần kiểm tra khi implement để không vô tình log `password` plaintext.

## 11. Auth state machine

```
                 ┌────────────────┐
                 │ UNAUTHENTICATED│
                 └───────┬────────┘
                         │ register / login thành công
                         ▼
                 ┌────────────────┐
                 │  AUTHENTICATED │
                 └───────┬────────┘
              logout │         │ token hết hạn (exp) hoặc bị revoke thủ công (xoá cookie)
                     ▼         ▼
                 ┌────────────────┐
                 │ UNAUTHENTICATED│
                 └────────────────┘
```

Frontend (thêm ở Phase 4):

```
   App khởi động
        │
        ▼
      UNKNOWN  ── chưa render Login hay App, tránh nhấp nháy Login lúc F5 ──
        │
        │ GET /auth/me
        │
   ┌────┴────┐
   200        401
   │           │
   ▼           ▼
AUTHENTICATED  UNAUTHENTICATED → render Login/Register
```

Nguyên tắc quan trọng: **không redirect sang Login ngay khi app khởi động** trước khi `/auth/me` trả lời — state ban đầu là `UNKNOWN`, không phải `UNAUTHENTICATED`, nếu không sẽ có hiện tượng flash màn hình Login mỗi lần F5 dù cookie vẫn còn hợp lệ.

## 12. Acceptance criteria

- [ ] Đăng ký với email chưa tồn tại → tài khoản được tạo, cookie được set, gọi `/auth/me` ngay sau đó trả đúng user vừa tạo.
- [ ] Đăng ký với email đã tồn tại (kể cả khi 2 request gửi đồng thời cùng email) → đúng 1 tài khoản được tạo, request còn lại nhận 409.
- [ ] Đăng ký với password < 8 hoặc > 64 ký tự → 422.
- [ ] Đăng nhập đúng email/password → cookie được set, `/auth/me` trả đúng user.
- [ ] Đăng nhập sai (email không tồn tại HOẶC sai password) → 401 với cùng 1 message, không phân biệt được 2 trường hợp từ response.
- [ ] Đăng xuất → cookie bị xoá, gọi lại `/auth/me` sau đó trả 401.
- [ ] Gọi `/auth/me` hoặc bất kỳ route nào cần auth mà không có cookie → 401.
- [ ] JWT hết hạn (`exp` đã qua) → mọi route cần auth trả 401, không crash 500.
- [ ] Sau khi migrate router (Phase 3): user A không đọc/sửa/xoá được resource (document, conversation, quiz, flashcard...) của user B, kể cả khi biết ID resource đó.
- [ ] Không có route nào còn nhận `user_id` từ query param hoặc request body sau Phase 3 (audit lại toàn bộ 8 router).
- [ ] `UserOut` ở mọi response không chứa `password_hash`.
