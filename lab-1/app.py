from fastapi import FastAPI, Request
from database import engine, SessionLocal
from models import Base, Visit
import datetime

# Создание таблиц в базе данных
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Visit Tracker API",
    description="API для отслеживания посещений",
    version="1.0.0"
)

@app.get("/hello")
async def hello(request: Request):
    """
    Эндпоинт /hello:
    1. Получает текущее время
    2. Получает IP-адрес клиента
    3. Сохраняет запись в таблицу Visit
    4. Возвращает "Hello"
    """
    
    # 1. Получаем текущее время
    now = datetime.datetime.utcnow()
    
    # 2. Получаем IP-адрес клиента
    client_ip = request.client.host
    
    # 3. Сохраняем запись в базу данных
    db = SessionLocal()
    try:
        visit = Visit(
            visit_time=now,
            client_ip=client_ip
        )
        db.add(visit)
        db.commit()
    finally:
        db.close()
    
    # 4. Возвращаем ответ
    return "Hello"

@app.get("/")
async def root():
    """
    Корневой эндпоинт для проверки работоспособности
    """
    return {
        "status": "ok",
        "message": "Visit Tracker API is running",
        "endpoints": {
            "/hello": "POST - Record a visit",
            "/": "GET - Health check"
        }
    }

@app.get("/health")
async def health():
    """
    Эндпоинт для проверки здоровья приложения
    """
    return {"status": "healthy"}