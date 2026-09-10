FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY wsgi.py .
RUN mkdir -p /data
ENV DATABASE=/data/homebuster.sqlite3
EXPOSE 8080
CMD ["gunicorn","--bind=0.0.0.0:8080","--workers=2","--threads=4","wsgi:app"]
