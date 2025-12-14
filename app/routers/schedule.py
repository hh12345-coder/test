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
from app.routers.team import get_current_user
from app.models.team import Team, TeamMember
from typing import Any
from pydantic import BaseModel
from typing import List, Dict
import datetime

router = APIRouter()

class ScheduleItem(BaseModel):
    day: str
    start: str
    end: str
    course: str = ""  # 课程名称
    weeks: List[int] = []  # 教学周列表，例如 [1,2,3,4,5]
    
class UserSchedule(BaseModel):
    user_id: int
    schedules: List[ScheduleItem]
    
class ExcludedTimeSlot(BaseModel):
    """排除的时间段"""
    day: str  # 周一-周日
    start: str  # HH:MM
    end: str  # HH:MM

class FreeTimeRequest(BaseModel):
    schedules: List[List[ScheduleItem]]
    week: int = 1
    excluded_times: List[ExcludedTimeSlot] = []  # 手动排除的时间段

@router.post("/upload")
async def upload_schedule(
    file: UploadFile = File(...),
    user_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    上传单个课表文件并解析为结构化课程列表，然后保存到数据库
    支持: .ics, .xlsx, .csv
    """
    print("🚀 ENTER /schedule/upload")
    
    if not file.filename.endswith(('.ics','.xlsx','.csv')):
        raise HTTPException(status_code=400, detail="文件格式不支持")
    
    content = await file.read()
    print(f"📄 FILE: {file.filename}, SIZE: {len(content)} bytes")
    
    try:
        # 打印解析器信息
        print(f"🔧 PARSER FUNCTION: {parse_schedule_file}")
        print(f"📂 PARSER MODULE: {parse_schedule_file.__module__}")
        print("📄 CALLING parse_schedule_file")
        # 解析课程表
        parsed_schedule = parse_schedule_file(file.filename, content)
        print(f"📊 PARSE RESULT: {parsed_schedule}")
        print(f"📊 RESULT LENGTH: {len(parsed_schedule) if hasattr(parsed_schedule, '__len__') else 'N/A'}")
        
        # 使用当前用户ID或提供的user_id（用于测试）
        actual_user_id = user_id or current_user.id
        
        # 先清空该用户的所有课程（可选：可以选择保留旧课程）
        db.query(Schedule).filter(Schedule.user_id == actual_user_id).delete()
        db.commit()
        
        # 保存解析后的课程到数据库
        saved_courses = []
        for course in parsed_schedule:
            # 保存教学周信息
            weeks_str = ",".join(map(str, course.get('weeks', [])))
            
            new_course = Schedule(
                user_id=actual_user_id,
                day=course['day'],
                start=course['start'],
                end=course['end'],
                course=course.get('course', ''),
                weeks=weeks_str
            )
            db.add(new_course)
            saved_courses.append(new_course)
        
        db.commit()
        
        # 返回保存后的课程信息
        return {
            "success": True,
            "data": [
                {
                    "day": course.day,
                    "start": course.start,
                    "end": course.end,
                    "course": course.course,
                    "weeks": [int(w.strip()) for w in course.weeks.split(",") if w.strip()]
                }
                for course in saved_courses
            ]
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    
@router.post("/upload/screenshot")
async def upload_screenshot(file: UploadFile = File(...)):
    """
    使用 DeepSeek 将课表截图解析为结构化 JSON。
    支持单个文件上传。
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
        return {"success": True, "source": "deepseek", "parsed": None, "model_text": None, "raw_response": j}

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
        return {"success": True, "source": "deepseek", "parsed": parsed, "raw_response": j}
    else:
        return {"success": True, "source": "deepseek", "parsed": parsed, "model_text": model_text, "raw_response": j}

@router.post("/upload/screenshots")
async def upload_screenshots(files: List[UploadFile] = File(...)):
    """
    批量上传多个课表截图并解析
    返回：{"results": [{"file_index": 0, "filename": "...", "parsed": {...}, ...}, ...]}
    """
    if not DEEPSEEK_API_KEY:
        raise HTTPException(status_code=400, detail="DEEPSEEK_API_KEY 未配置。请在 .env 中设置。")
    
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="请至少上传一个文件")
    
    results = []
    
    for idx, file in enumerate(files):
        try:
            content = await file.read()
            if not content:
                results.append({
                    "file_index": idx,
                    "filename": file.filename,
                    "success": False,
                    "error": "文件为空"
                })
                continue
            
            # 把图片 base64 编码
            b64 = base64.b64encode(content).decode("ascii")
            data_uri = f"data:{file.content_type};base64,{b64}"
            
            system_prompt = (
                "你是一个结构化表格解析助手。输入为大学课表截图，请严格提取每一门课程的字段："
                "course（课程名字符串），weekday（1-7 整数，1表示周一，7表示周日），start_time（时间字符串，格式HH:MM），end_time（时间字符串，格式HH:MM），"
                "weeks（整数列表，表示哪些周有课），room（可选），teacher（可选）。"
                "请**只返回一个 JSON 对象**，格式为 {\"courses\": [{\"course\": \"课程名\", \"weekday\": 1, \"start_time\": \"08:00\", \"end_time\": \"09:40\", \"weeks\": [1,2,3,...], ...}, ...]}，不要返回其他解释性文字。"
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
                "max_tokens": 2000,
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
                    results.append({
                        "file_index": idx,
                        "filename": file.filename,
                        "success": False,
                        "error": f"网络错误: {e}"
                    })
                    continue
            
            if resp.status_code != 200:
                results.append({
                    "file_index": idx,
                    "filename": file.filename,
                    "success": False,
                    "error": f"API返回错误: {resp.status_code}"
                })
                continue
            
            j = resp.json()
            
            # 提取模型返回文本
            model_text = None
            try:
                if "choices" in j and len(j["choices"]) > 0:
                    choice = j["choices"][0]
                    if isinstance(choice.get("message"), dict):
                        model_text = choice["message"].get("content")
                    elif choice.get("text"):
                        model_text = choice.get("text")
            except Exception:
                pass
            
            if not model_text:
                results.append({
                    "file_index": idx,
                    "filename": file.filename,
                    "success": False,
                    "error": "无法获取模型返回文本"
                })
                continue
            
            # 解析JSON
            parsed = None
            try:
                parsed = json.loads(model_text)
            except json.JSONDecodeError:
                import re
                m = re.search(r'(\{[\s\S]*\})', model_text)
                if m:
                    try:
                        parsed = json.loads(m.group(1))
                    except Exception:
                        pass
            
            if parsed and isinstance(parsed, dict) and "courses" in parsed:
                # 转换格式为标准格式
                courses = parsed.get("courses", [])
                schedule_items = []
                weekday_map = {1: "周一", 2: "周二", 3: "周三", 4: "周四", 5: "周五", 6: "周六", 7: "周日"}
                
                for course in courses:
                    weekday = course.get("weekday")
                    if weekday and weekday in weekday_map:
                        schedule_items.append({
                            "day": weekday_map[weekday],
                            "start": course.get("start_time", ""),
                            "end": course.get("end_time", ""),
                            "course": course.get("course", ""),
                            "weeks": course.get("weeks", [])
                        })
                
                results.append({
                    "file_index": idx,
                    "filename": file.filename,
                    "success": True,
                    "parsed": {"courses": schedule_items},
                    "schedule": schedule_items
                })
            else:
                results.append({
                    "file_index": idx,
                    "filename": file.filename,
                    "success": False,
                    "error": "解析结果格式不正确",
                    "model_text": model_text[:200]  # 只返回前200字符用于调试
                })
        except Exception as e:
            results.append({
                "file_index": idx,
                "filename": file.filename,
                "success": False,
                "error": str(e)
            })
    
    return {"success": True, "results": results}

@router.post("/save")
async def save_schedule(
    schedule_data: List[ScheduleItem],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    保存用户的课表到数据库
    """
    try:
        # 先删除用户旧的课表
        db.query(Schedule).filter(Schedule.user_id == current_user.id).delete()
        
        # 保存新课表
        for item in schedule_data:
            # 将weeks列表转换为逗号分隔的字符串
            weeks_str = ",".join(map(str, item.weeks)) if item.weeks else ""
            schedule = Schedule(
                user_id=current_user.id,
                day=item.day,
                start=item.start,
                end=item.end,
                weeks=weeks_str
            )
            db.add(schedule)
        
        db.commit()
        return {"success": True, "message": "课表保存成功", "count": len(schedule_data)}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/my")
async def get_my_schedule(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取当前用户的课表
    """
    # 星期映射表，用于统一不同格式的星期值
    day_map = {
        # 数字格式
        "1": "周一",
        "2": "周二",
        "3": "周三",
        "4": "周四",
        "5": "周五",
        "6": "周六",
        "7": "周日",
        
        # 全称格式
        "星期一": "周一",
        "星期二": "周二",
        "星期三": "周三",
        "星期四": "周四",
        "星期五": "周五",
        "星期六": "周六",
        "星期日": "周日",
        
        # 英文格式
        "Monday": "周一",
        "Mon": "周一",
        "Tuesday": "周二",
        "Tue": "周二",
        "Wednesday": "周三",
        "Wed": "周三",
        "Thursday": "周四",
        "Thu": "周四",
        "Friday": "周五",
        "Fri": "周五",
        "Saturday": "周六",
        "Sat": "周六",
        "Sunday": "周日",
        "Sun": "周日"
    }
    
    # 定义默认的教学周范围（1-16周）
    ALL_WEEKS = list(range(1, 17))
    
    schedules = db.query(Schedule).filter(Schedule.user_id == current_user.id).all()
    return {
        "schedules": [
            {
                "day": day_map.get(s.day, s.day),  # 标准化星期格式
                "start": s.start, 
                "end": s.end,
                "weeks": [int(w.strip()) for w in s.weeks.split(",") if w.strip()] or ALL_WEEKS  # 无指定教学周则默认每周都有
            }
            for s in schedules
        ]
    }

@router.post("/team/{team_id}/free_times")
async def compute_team_free_times(
    team_id: int,
    req: FreeTimeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    计算团队成员的共同空闲时间
    自动获取所有团队成员的课表，并计算共同空闲时间
    """
    # 验证用户是否是团队成员
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="团队不存在")
    
    is_member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == current_user.id
    ).first()
    
    if not is_member and team.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问此团队")
    
    # 获取所有团队成员的课表
    members = db.query(TeamMember).filter(TeamMember.team_id == team_id).all()
    all_schedules = []
    
    # 星期映射表，用于统一不同格式的星期值
    day_map = {
        # 数字格式
        "1": "周一",
        "2": "周二",
        "3": "周三",
        "4": "周四",
        "5": "周五",
        "6": "周六",
        "7": "周日",
        
        # 全称格式
        "星期一": "周一",
        "星期二": "周二",
        "星期三": "周三",
        "星期四": "周四",
        "星期五": "周五",
        "星期六": "周六",
        "星期日": "周日",
        
        # 英文格式
        "Monday": "周一",
        "Mon": "周一",
        "Tuesday": "周二",
        "Tue": "周二",
        "Wednesday": "周三",
        "Wed": "周三",
        "Thursday": "周四",
        "Thu": "周四",
        "Friday": "周五",
        "Fri": "周五",
        "Saturday": "周六",
        "Sat": "周六",
        "Sunday": "周日",
        "Sun": "周日"
    }
    
    # 定义默认的教学周范围（1-16周）
    ALL_WEEKS = list(range(1, 17))
    
    for member in members:
        user_schedules = db.query(Schedule).filter(Schedule.user_id == member.user_id).all()
        member_schedule = [
            ScheduleItem(
                day=day_map.get(s.day, s.day),  # 标准化星期格式
                start=s.start, 
                end=s.end,
                weeks=[int(w.strip()) for w in s.weeks.split(",") if w.strip()] or ALL_WEEKS  # 无指定教学周则默认每周都有
            )
            for s in user_schedules
        ]
        if member_schedule:
            all_schedules.append(member_schedule)
    
    # 合并传入的课表（如果有临时上传的课表）
    if req.schedules:
        all_schedules.extend(req.schedules)
    
    if not all_schedules:
        raise HTTPException(status_code=400, detail="团队成员都没有课表，请先上传课表")
    
    # 使用合并后的课表计算空闲时间
    new_req = FreeTimeRequest(
        schedules=all_schedules,
        week=req.week,
        excluded_times=req.excluded_times
    )
    
    return await compute_free_times(new_req, db)

@router.post("/free_times")
async def compute_free_times(req: FreeTimeRequest, db: Session = Depends(get_db)):
    """
    计算多用户共同空闲时间（含教学周、节假日、最优时段推荐）
    返回格式: { 
        "free_times": [{"day": "周一", "start": "10:00", "end": "12:00", "duration_min": 120}, ...],
        "recommended_time": {...},
        "total_free_slots": 45
    }
    """
    try:
        from app.utils.calendar_utils import is_holiday, in_teaching_week, FIRST_WEEK_START
        
        valid_days = ['周一', '周二', '周三', '周四', '周五']
        current_week = req.week or 1
        
        # 初始化：08:00-22:00，30分钟粒度 = 28个块
        # True表示已占用，False表示空闲
        time_blocks = {day: [False] * 28 for day in valid_days}
        
        # 构建本周日期映射
        week_start = FIRST_WEEK_START + datetime.timedelta(weeks=current_week - 1)
        date_map = {i: week_start + datetime.timedelta(days=i) for i in range(5)}
        
        # 星期映射表，处理不同格式的星期表示
        day_map = {
            '1': '周一', '星期一': '周一', 'Monday': '周一',
            '2': '周二', '星期二': '周二', 'Tuesday': '周二',
            '3': '周三', '星期三': '周三', 'Wednesday': '周三',
            '4': '周四', '星期四': '周四', 'Thursday': '周四',
            '5': '周五', '星期五': '周五', 'Friday': '周五'
        }
        
        # 遍历所有用户课程，标记占用时间
        for user_schedule in req.schedules:
            for course in user_schedule:
                day = course.day
                
                # 标准化星期表示
                day = day_map.get(day, day)
                
                if day not in valid_days:
                    continue
                
                # 检查课程是否在当前教学周
                # 如果课程没有指定教学周，默认认为“每周都有”
                if course.weeks:
                    if current_week not in course.weeks:
                        continue  # 当前周没有这门课，跳过
                
                weekday_idx = valid_days.index(day)
                course_date = date_map[weekday_idx]
                
                # 跳过节假日
                if is_holiday(course_date):
                    continue
                
                # 解析时间
                try:
                    start_h, start_m = map(int, course.start.split(':'))
                    end_h, end_m = map(int, course.end.split(':'))
                except:
                    continue
                
                # 转换为30分钟块索引（08:00 为第0块）
                start_block = max(0, (start_h - 8) * 2 + (start_m // 30))
                end_block = min(28, (end_h - 8) * 2 + (end_m // 30) + (1 if end_m % 30 else 0))
                
                # 标记该课程时段为占用
                for b in range(start_block, end_block):
                    time_blocks[day][b] = True
        
        # 处理手动排除的时间段
        for excluded in req.excluded_times:
            day = excluded.day
            if day not in valid_days:
                continue
            
            try:
                start_h, start_m = map(int, excluded.start.split(':'))
                end_h, end_m = map(int, excluded.end.split(':'))
            except:
                continue
            
            # 转换为30分钟块索引
            start_block = max(0, (start_h - 8) * 2 + (start_m // 30))
            end_block = min(28, (end_h - 8) * 2 + (end_m // 30) + (1 if end_m % 30 else 0))
            
            # 标记该时段为占用
            for b in range(start_block, end_block):
                time_blocks[day][b] = True
        
        # 提取连续的空闲时段
        free_times = []
        for day in valid_days:
            start_block = None
            for i in range(28):
                if not time_blocks[day][i] and start_block is None:
                    start_block = i
                elif (time_blocks[day][i] or i == 27) and start_block is not None:
                    end_block = i if time_blocks[day][i] else i + 1
                    
                    start_hour = 8 + start_block // 2
                    start_min = (start_block % 2) * 30
                    end_hour = 8 + end_block // 2
                    end_min = (end_block % 2) * 30
                    
                    duration = (end_block - start_block) * 30
                    
                    free_times.append({
                        'day': day,
                        'start': f'{start_hour:02d}:{start_min:02d}',
                        'end': f'{end_hour:02d}:{end_min:02d}',
                        'duration_min': duration
                    })
                    start_block = None
        
        # 按推荐度排序：优先下午3点左右的时段（避免晚课）
        def score_time(item):
            hour = int(item['start'].split(':')[0])
            day_idx = valid_days.index(item['day'])
            # 主要按周数（平均分布），次要按时间（14-16点最优）
            dist_from_ideal = abs(hour - 15)
            return (day_idx, dist_from_ideal, -item['duration_min'])
        
        free_times.sort(key=score_time)
        
        return {
            'success': True,
            'free_times': free_times,
            'recommended_time': free_times[0] if free_times else None,
            'current_week': current_week,
            'total_free_slots': sum(day_blocks.count(False) for day_blocks in time_blocks.values())
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))