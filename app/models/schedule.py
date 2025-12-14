from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    day = Column(String(10))
    start = Column(String(10))
    end = Column(String(10))
    weeks = Column(String(100), default="")  # 存储教学周，格式如 "1,2,3,4,5"
    course = Column(String(50), default="")  # 课程名称
    
    # 关系
    user = relationship("User", back_populates="schedules")