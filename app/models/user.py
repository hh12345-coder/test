from sqlalchemy import Column, Integer, String
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    openid = Column(String(50), unique=True, index=True)   # 小程序用户唯一ID
    nickname = Column(String(100))