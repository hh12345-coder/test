from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from app.database import get_db
from app.models.school import School

router = APIRouter()

class SchoolResponse(BaseModel):
    """学校响应"""
    id: int
    name: str
    lat: float
    lon: float
    city: Optional[str] = None
    province: Optional[str] = None
    
    class Config:
        from_attributes = True

# 预定义的学校数据（上海地区主要高校）- 已更新为更准确的坐标
DEFAULT_SCHOOLS = [
    {"name": "上海财经大学", "lat": 31.304208, "lon": 121.506379, "city": "上海", "province": "上海"},
    {"name": "复旦大学", "lat": 31.293647, "lon": 121.507235, "city": "上海", "province": "上海"},
    {"name": "同济大学", "lat": 31.296882, "lon": 121.496579, "city": "上海", "province": "上海"},
    {"name": "华东师范大学", "lat": 31.156754, "lon": 121.425737, "city": "上海", "province": "上海"},
    {"name": "上海交通大学（徐汇）", "lat": 31.192711, "lon": 121.437543, "city": "上海", "province": "上海"},
    {"name": "上海交通大学（闵行）", "lat": 31.121552, "lon": 121.436926, "city": "上海", "province": "上海"},
    {"name": "上海大学（宝山）", "lat": 31.318855, "lon": 121.487706, "city": "上海", "province": "上海"},
]

@router.get("", response_model=List[SchoolResponse])
def list_schools(db: Session = Depends(get_db)):
    """获取所有学校列表"""
    schools = db.query(School).all()
    
    # 如果数据库中没有学校，初始化默认学校
    if not schools:
        for school_data in DEFAULT_SCHOOLS:
            school = School(**school_data)
            db.add(school)
        db.commit()
        schools = db.query(School).all()
    
    return schools

@router.get("/{school_id}", response_model=SchoolResponse)
def get_school(school_id: int, db: Session = Depends(get_db)):
    """获取学校详情"""
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="学校不存在")
    return school

@router.post("", response_model=SchoolResponse)
def create_school(name: str, lat: float, lon: float, city: Optional[str] = None, province: Optional[str] = None, db: Session = Depends(get_db)):
    """创建新学校（管理员功能）"""
    # 检查是否已存在
    existing = db.query(School).filter(School.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail="学校已存在")
    
    school = School(name=name, lat=lat, lon=lon, city=city, province=province)
    db.add(school)
    db.commit()
    db.refresh(school)
    return school

