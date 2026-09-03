from sqlalchemy import Column, Integer, String, DateTime
from database import Base
import datetime

class Visit(Base):
    """
    Модель Visit - хранит информацию о посещениях
    """
    __tablename__ = "visits"

    # Первичный ключ
    id = Column(Integer, primary_key=True, index=True)
    
    # Время обращения 
    visit_time = Column(DateTime, default=datetime.datetime.utcnow)
    
    client_ip = Column(String, nullable=False)