from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    openid = Column(String(50), unique=True, index=True)   # 小程序用户唯一ID
    nickname = Column(String(100))
    school = Column(String(100))  # 学校名称
    lat = Column(String(50))  # 学校纬度
    lon = Column(String(50))  # 学校经度
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    schedules = relationship("Schedule", back_populates="user")
    teams_owned = relationship("Team", foreign_keys="Team.owner_id")
    team_memberships = relationship("TeamMember", back_populates="user")