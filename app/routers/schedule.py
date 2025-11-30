# app/routers/schedule.py
import base64
import json
import httpx
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from app.utils.schedule_parser import parse_schedule_file
from app.utils.calendar_utils import is_holiday, in_teaching_week
from app.config import DEEPSEEK_API_KEY, DEEPSEEK_API_BASE
from app.database import get_db
from app.models import User, Schedule
from typing import Any
from pydantic import BaseModel
from typing import List, Dict
import datetime

router = APIRouter()

class ScheduleItem(BaseModel):
    day: str
    start: str
    end: str
    
class UserSchedule(BaseModel):
    user_id: int
    schedules: List[ScheduleItem]
    
class FreeTimeRequest(BaseModel):
    schedules: List[List[ScheduleItem]]
    week: int = 1

@router.post("/upload")
async def upload_schedule(file: UploadFile = File(...)):
    """
    上传单个课表文件并解析为结构化课程列表
    支持: .ics, .xlsx
    """
    if not file.filename.endswith(('.ics','.xlsx')):
        raise HTTPException(status_code=400, detail="文件格式不支持")
    
    content = await file.read()
    
    try:
        schedule = parse_schedule_file(file.filename, content)
        return {"data": schedule}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"课表解析失败: {e}")
    
@router.post("/upload/screenshot")
async def upload_screenshot(file: UploadFile = File(...)):
    """
    使用 DeepSeek 将课表截图解析为结构化 JSON。
    需要在 .env 中配置 DEEPSEEK_API_KEY（可选 DEEPSEEK_API_BASE）。
    返回：
      - 成功：{"source":"deepseek","parsed": {...}, "raw_response": {...}}
      - 失败或模型输出不可解析 JSON：返回原始模型文本和 raw_response，便于调试
    """
    if not DEEPSEEK_API_KEY:
        raise HTTPException(status_code=400, detail="DEEPSEEK_API_KEY 未配置。请在 .env 中设置。")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")

    # 把图片 base64 编码
    b64 = base64.b64encode(content).decode("ascii")
    data_uri = f"data:{file.content_type};base64,{b64}"

    system_prompt = (
        "你是一个结构化表格解析助手。输入为大学课表截图，请严格提取每一门课程的字段："
        "course（课程名字符串），weekday（1-7 整数），start_slot（整数节次），end_slot（整数节次），weeks（整数列表），"
        "room（可选），teacher（可选）。"
        "请**只返回一个 JSON 对象**，格式为 {\"courses\": [{...}, ...]}，不要返回其他解释性文字。"
    )
    user_prompt = "请解析这张课表截图并以 JSON 输出（按上面的字段说明）。"

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "images": [
            {"type": "input_image", "image": data_uri}
        ],
        "max_tokens": 1200,
        "temperature": 0.0
    }

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(f"{DEEPSEEK_API_BASE.rstrip('/')}/chat/completions", json=payload, headers=headers)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"调用 DeepSeek 网络错误: {e}")

    if resp.status_code != 200:
        # 把返回的状态和文本直接返回，便于排查 Key/权限/配额问题
        raise HTTPException(status_code=502, detail={"status_code": resp.status_code, "body": resp.text})

    j = resp.json()

    # 尝试从常见位置抽取模型返回文本
    model_text = None
    try:
        if "choices" in j and len(j["choices"]) > 0:
            choice = j["choices"][0]
            # 较新的 API 返回 choice.message.content
            if isinstance(choice.get("message"), dict):
                model_text = choice["message"].get("content")
            elif choice.get("text"):
                model_text = choice.get("text")
    except Exception:
        model_text = None

    # 如果没有拿到模型文本，返回原始 JSON 以便排查
    if not model_text:
        return {"source": "deepseek", "parsed": None, "model_text": None, "raw_response": j}

    # 尝试解析出 JSON
    parsed = None
    try:
        parsed = json.loads(model_text)
    except json.JSONDecodeError:
        # 尝试抽取第一段 JSON 子串
        import re
        m = re.search(r'(\{[\s\S]*\})', model_text)
        if m:
            try:
                parsed = json.loads(m.group(1))
            except Exception:
                parsed = None

    # 如果解析成功并且包含 courses 字段就返回，否则把模型文本和原始响应都返回
    if parsed and isinstance(parsed, dict) and "courses" in parsed:
        return {"source": "deepseek", "parsed": parsed, "raw_response": j}
    else:
        return {"source": "deepseek", "parsed": parsed, "model_text": model_text, "raw_response": j}

@router.post("/free_times")
async def compute_free_times(req: FreeTimeRequest, db: Session = Depends(get_db)):
    """计算多用户共同空闲时间，支持教学周和节假日过滤"""
    start_date = datetime.date(2025, 2, 24)  # 开学日（可配置）
    current_week = req.week                  # 前端传入当前教学周

    valid_days = ['周一','周二','周三','周四','周五']

    # 初始化时间块为空闲（True表示空闲）
    time_blocks = {day: [True]*24 for day in valid_days}

    for user_schedule in req.schedules:
        for item in user_schedule:
            # 星期转换
            day = item.day  
            if day not in valid_days:
                continue
            
            # 节假日过滤
            weekday_num = valid_days.index(day)
            date = start_date + datetime.timedelta(days=weekday_num)
            if is_holiday(date):
                continue

            # 教学周过滤
            if not in_teaching_week(start_date, current_week, date):
                continue

            # 占用时间
            try:
                s = int(item.start.split(":")[0])
                e = int(item.end.split(":")[0])
                # 确保范围有效
                s = max(0, min(23, s))
                e = max(s+1, min(24, e))
                for h in range(s, e):
                    time_blocks[day][h] = False
            except (ValueError, IndexError):
                continue  # 忽略无效的时间格式

    # 找出所有空闲时间段
    free_times = []
    for day in valid_days:
        hour = 0
        while hour < 24:
            if time_blocks[day][hour]:
                # 找到空闲时间段的开始
                start_hour = hour
                # 找到空闲时间段的结束
                while hour < 24 and time_blocks[day][hour]:
                    hour += 1
                end_hour = hour
                # 添加空闲时间段
                free_times.append({
                    "day": day,
                    "start": f"{start_hour:02d}:00",
                    "end": f"{end_hour:02d}:00"
                })
            else:
                hour += 1

    return {"free_times": free_times, "current_week": current_week}