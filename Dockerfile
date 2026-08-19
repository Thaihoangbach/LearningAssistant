FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./backend/app

WORKDIR /app/backend

EXPOSE 8000

# ./data (DB, uploads, vectorstore) resolve tương đối theo CWD này — mount
# volume đúng /app/backend/data để dữ liệu không mất khi container restart.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
