# --- стадия сборки: зависимости
FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- стадия запуска
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PORT=8000 \
    LOG_LEVEL=INFO
RUN useradd --create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=builder /install /usr/local
COPY adapters ./adapters
COPY application ./application
COPY domain ./domain
COPY infrastructure ./infrastructure
COPY wsgi.py gunicorn.conf.py ./
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/health')"
CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
