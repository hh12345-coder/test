from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import os
import requests
from datetime import datetime, timedelta
try:
    import jwt  # PyJWT库
except ImportError:
    import logging
    logging.warning("PyJWT库未安装，将使用模拟实现")
    # 简单的模拟实现，仅用于测试
    class MockJWT:
        @staticmethod
        def encode(payload, key, algorithm=None):
            return "mock_token_" + payload.get("sub", "unknown")
    jwt = MockJWT()

from app.database import SessionLocal
from app.models.user import User

router = APIRouter(tags=["authentication"])

# 从环境变量获取密钥
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")

# 登录请求模型
class LoginRequest(BaseModel):
    code: str

# 数据库依赖
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 生成JWT token
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=7)  # 7天过期
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")
    return encoded_jwt

@router.post("/login")
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    """
    小程序登录接口
    通过微信code换取openid并生成token
    """
    try:
        # 这里模拟微信接口调用，实际项目中需要使用微信官方的API
        # 微信接口：https://api.weixin.qq.com/sns/jscode2session
        # 由于无法调用真实接口，这里使用模拟的openid
        # 在实际开发中，应该使用真实的微信接口调用
        # 这里仅为演示，实际生产环境需要替换为真实的微信接口调用
        openid = f"mock_openid_{req.code[:10]}"
        
        # 查询用户是否存在
        user = db.query(User).filter(User.openid == openid).first()
        
        if not user:
            # 创建新用户
            user = User(
                openid=openid,
                nickname=f"用户_{openid[-6:]}"
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        
        # 生成token
        token = create_access_token(data={"sub": str(user.id), "openid": user.openid})
        
        return {
            "success": True,
            "data": {
                "token": token,
                "user": {
                    "id": user.id,
                    "nickname": user.nickname
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail={"success": False, "message": str(e)})
