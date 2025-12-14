from sqlalchemy import Column, Integer, String, Float
from app.database import Base

class School(Base):
    """学校表"""
    __tablename__ = "schools"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    lat = Column(Float, nullable=False)  # 纬度
    lon = Column(Float, nullable=False)  # 经度
    city = Column(String(50))  # 城市
    province = Column(String(50))  # 省份

