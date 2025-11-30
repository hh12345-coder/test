from sqlalchemy import Column, Integer, String, ForeignKey
from app.database import Base

class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    day = Column(String(10))
    start = Column(String(10))
    end = Column(String(10))