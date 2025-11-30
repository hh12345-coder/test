from datetime import datetime, date, timedelta

# 定义教学周开始日期（示例：2023年9月1日作为第1周开始）
FIRST_WEEK_START = date(2023, 9, 1)

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
    """
    # 判断是否为周末
    if date_obj.weekday() in [5, 6]:
        return True
    # 判断是否为主要节假日
    holiday_key = (date_obj.month, date_obj.day)
    return holiday_key in CHINA_HOLIDAYS

def in_teaching_week(date_obj):
    """
    判断给定日期是否在教学周内
    """
    delta_weeks = (date_obj - FIRST_WEEK_START).days // 7
    return 0 <= delta_weeks < TOTAL_TEACHING_WEEKS

def get_current_teaching_week():
    """
    获取当前教学周
    """
    today = date.today()
    delta_weeks = (today - FIRST_WEEK_START).days // 7 + 1
    if 1 <= delta_weeks <= TOTAL_TEACHING_WEEKS:
        return delta_weeks
    return 1  # 默认返回第1周