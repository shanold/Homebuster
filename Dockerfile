FROM python:3.13-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATABASE_PATH=/data/movies.db
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /data
EXPOSE 8000
CMD ["gunicorn", "--name", "Homebuster", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "--timeout", "60", "app:app"]
