FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./backend/app
COPY backend/alembic ./backend/alembic
COPY backend/alembic.ini ./backend/alembic.ini
COPY docker-entrypoint.sh ./docker-entrypoint.sh
RUN chmod +x ./docker-entrypoint.sh

WORKDIR /app/backend

EXPOSE 8000

# Không còn volume/đĩa bền vững nào cần mount — DB (Postgres), vector
# embedding (pgvector, cùng DB) và file gốc đã tải lên (Backblaze B2, xem
# app/storage.py) đều sống NGOÀI container. Image này hoàn toàn stateless,
# khớp đúng yêu cầu của các host free tier không có đĩa bền vững (Render).
ENTRYPOINT ["../docker-entrypoint.sh"]
