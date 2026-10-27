FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py .
RUN useradd --create-home app
USER app
ENV APP_MODULE=app_sync:app
CMD ["sh", "-c", "exec uvicorn $APP_MODULE --host 0.0.0.0 --port 8000 --workers 1"]
