from datetime import datetime, date, timedelta

# 定义教学周开始日期（2024年秋季学期示例）
FIRST_WEEK_START = date(2024, 9, 2)

# 定义总教学周数
TOTAL_TEACHING_WEEKS = 20

# 简化的节假日列表（主要节假日）
CHINA_HOLIDAYS = {
    (1, 1),  # 元旦
    (2, 14), (2, 15), (2, 16), (2, 17), (2, 18), (2, 19), (2, 20),  # 春节
    (4, 4), (4, 5), (4, 6),  # 清明节
    (5, 1), (5, 2), (5, 3),  # 劳动节
    (6, 10), (6, 11), (6, 12),  # 端午节
    (9, 15), (9, 16), (9, 17),  # 中秋节
    (10, 1), (10, 2), (10, 3), (10, 4), (10, 5), (10, 6), (10, 7)  # 国庆节
}

def is_holiday(date_obj):
    """
    判断给定日期是否为节假日（简化版本）
    注意：这里只判断法定节假日，不判断周末，因为我们需要计算周一到周五的课程
    """
    # 判断是否为主要节假日
    holiday_key = (date_obj.month, date_obj.day)
    return holiday_key in CHINA_HOLIDAYS

def in_teaching_week(base_date, target_week, check_date):
    """
    判断给定日期是否在指定教学周内
    base_date: 教学周开始日期
    target_week: 目标教学周（1-20）
    check_date: 要检查的日期
    """
    week_start = base_date + timedelta(weeks=target_week - 1)
    week_end = week_start + timedelta(days=6)
    return week_start <= check_date <= week_end

def get_current_teaching_week(base_date=FIRST_WEEK_START):
    """
    获取当前教学周
    """
    today = date.today()
    delta_days = (today - base_date).days
    if delta_days < 0:
        return 1
    current_week = (delta_days // 7) + 1
    if 1 <= current_week <= TOTAL_TEACHING_WEEKS:
        return current_week
    return TOTAL_TEACHING_WEEKS