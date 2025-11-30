from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.place import router as place_router
from app.routers.schedule import router as schedule_router
from app.routers.auth import router as auth_router
from app.database import Base, engine
from app.models import user, schedule

# 创建数据库表
Base.metadata.create_all(bind=engine)

app = FastAPI(title="智能跨校约饭系统 API")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}

# 注册路由
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(place_router, prefix="/api/places", tags=["Place Recommendation"])
app.include_router(schedule_router, prefix="/api/schedule", tags=["Schedule Parsing"])
