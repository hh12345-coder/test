import io
import re
import pandas as pd
from icalendar import Calendar

DEFAULT_WEEKS = list(range(1, 17))  # 默认整个学期（1~16周）

def parse_schedule_file(filename: str, content: bytes):
    """
    解析课表文件（支持 .ics、.xlsx 和 .csv 格式）
    返回: [{"day": "周一", "start": "10:00", "end": "12:00", "course": "高数"}, ...]
    
    智能检测：
    1. 首先根据文件扩展名尝试解析
    2. 如果解析失败，尝试用其他格式的解析器来解析
    3. 提高系统的容错性
    """
    result = None
    
    # 先根据文件扩展名尝试解析
    try:
        if filename.endswith('.xlsx'):
            result = parse_excel(content)
        elif filename.endswith('.csv'):
            result = parse_csv(content)
        elif filename.endswith('.ics'):
            result = parse_ics(content)
        else:
            # 如果扩展名不匹配，尝试智能检测
            raise ValueError("不支持的文件格式，尝试智能检测")
    except Exception as e:
        # 扩展名解析失败，尝试智能检测文件内容
        print(f"根据扩展名解析失败: {e}，尝试智能检测文件内容")
        
        # 尝试解析为CSV
        try:
            result = parse_csv(content)
            print("智能检测: 文件实际是CSV格式")
        except Exception as csv_e:
            print(f"不是CSV格式: {csv_e}")
            
        # 尝试解析为Excel
        if result is None:
            try:
                result = parse_excel(content)
                print("智能检测: 文件实际是Excel格式")
            except Exception as excel_e:
                print(f"不是Excel格式: {excel_e}")
                
        # 尝试解析为ICS
        if result is None:
            try:
                result = parse_ics(content)
                print("智能检测: 文件实际是ICS格式")
            except Exception as ics_e:
                print(f"不是ICS格式: {ics_e}")
            
        # 所有格式都尝试过了，仍然失败
        if result is None:
            raise ValueError(f"无法解析文件。请确保文件格式为 .ics、.xlsx 或 .csv: {e}")

    # 强制校验解析结果结构
    print("🔍 VALIDATING PARSE RESULT")
    if not result:
        raise ValueError("解析结果为空")
    
    for item in result:
        if not all(k in item for k in ['day', 'start', 'end']):
            print(f"❌ INVALID ITEM: {item}")
            raise ValueError("解析结果缺少 day/start/end 字段")
    
    print("✅ VALIDATION PASSED")
    return result

def parse_excel(content: bytes):
    """
    解析 Excel 课表
    支持多种格式：
    1. 列名为 Day/Start/End/Course
    2. 列名为 日期/开始时间/结束时间/课程
    3. 列名为 星期/开始时间/结束时间/课程名称
    4. 自动检测课程表模式（行为天，列为节次）
    5. 上财矩阵型课表（星期×节次结构）
    """
    print("🔥 USING NEW parse_excel VERSION 🔥")
    try:
        # 首先尝试解析上财矩阵型课表（使用header=None保持原始结构）
        original_df = pd.read_excel(io.BytesIO(content), sheet_name=0, engine='openpyxl', header=None)
        
        # 保存原始列名用于调试
        original_columns = original_df.columns.tolist()
        print(f"原始列名: {original_columns}")
        
        try:
            result = parse_sufe_matrix_excel(original_df)
            print("成功解析为上财矩阵型课表")
            return result
        except Exception as e:
            print(f"上财矩阵课表解析失败: {e}")
    except Exception as e:
        raise ValueError(f"读取 Excel 失败: {str(e)}")

    # 如果不是上财矩阵型课表，再以常规方式读取文件（使用默认header=0）
    try:
        df = pd.read_excel(io.BytesIO(content), sheet_name=0, engine='openpyxl')
    except Exception as e:
        raise ValueError(f"读取 Excel 失败: {str(e)}")

    # 标准化列名
    df.columns = [col.lower().strip() for col in df.columns]
    print(f"标准化后列名: {df.columns.tolist()}")

    # 支持的列名映射（包含教学周）
    # 注意：键是我们内部使用的字段名，值是可能的列名
    possible_column_names = {
        'day': ['day', '日期', '星期', '周几', '星期几'],
        'start': ['start', '开始时间', '上课时间', '开始', '时间'],
        'end': ['end', '结束时间', '下课时间', '结束'],
        'course': ['course', '课程', '课程名称', '科目'],
        'weeks': ['weeks', '教学周', '周次', '周数']
    }

    # 自动检测列名映射
    detected_mapping = {}
    for field, possible_names in possible_column_names.items():
        for name in possible_names:
            if name in df.columns:
                detected_mapping[field] = name
                break
    print(f"检测到的列名映射: {detected_mapping}")

    # 检查是否找到了所有必要的列
    required_fields = ['day', 'start', 'end']
    if all(field in detected_mapping for field in required_fields):
        schedule = []
        for _, row in df.iterrows():
            day = str(row[detected_mapping['day']]).strip()
            start = str(row[detected_mapping['start']]).strip()
            end = str(row[detected_mapping['end']]).strip()
            course = str(row.get(detected_mapping.get('course', ''), '')).strip()
            weeks_str = str(row.get(detected_mapping.get('weeks', ''), '')).strip()

            # 解析教学周
            weeks = []
            if weeks_str and weeks_str != 'nan':
                if '-' in weeks_str:
                    # 范围格式，如 '1-8'
                    try:
                        start_week, end_week = map(int, weeks_str.split('-'))
                        weeks = list(range(start_week, end_week + 1))
                    except ValueError:
                        pass
                elif ',' in weeks_str:
                    # 逗号分隔格式，如 '1,3,5'
                    weeks = [int(w) for w in weeks_str.split(',') if w.strip().isdigit()]
                else:
                    # 尝试直接转换为整数
                    try:
                        weeks = [int(weeks_str)]
                    except ValueError:
                        weeks = []
                
                # 额外处理常见的教学周格式，如 "第1-8周"
                if not weeks and '周' in weeks_str:
                    import re
                    week_ranges = re.findall(r'(\d+)-(\d+)周', weeks_str)
                    if week_ranges:
                        for start_w, end_w in week_ranges:
                            try:
                                weeks.extend(range(int(start_w), int(end_w) + 1))
                            except ValueError:
                                pass
                        # 去重并排序
                        weeks = sorted(list(set(weeks)))
                
            # 基础校验
            if day and start and end:
                schedule_item = {
                    'day': day,
                    'start': start,
                    'end': end,
                    'course': course
                }
                # 如果没有明确周次，默认整个学期
                if not weeks:
                    weeks = DEFAULT_WEEKS
                schedule_item['weeks'] = weeks
                schedule.append(schedule_item)

        if schedule:
            return schedule

    # 自动检测课程表模式（行为天，列为节次）
    if '周一' in df.columns:
        schedule = []
        for day in ['周一', '周二', '周三', '周四', '周五', '周六', '周日']:
            if day in df.columns:
                for index, value in df[day].items():
                    if pd.notna(value):
                        schedule.append({
                            'day': day,
                            'start': f"{index + 1}:00",
                            'end': f"{index + 2}:00",
                            'course': str(value).strip(),
                            'weeks': DEFAULT_WEEKS  # 默认整个学期
                        })
        if schedule:
            return schedule

    raise ValueError("Excel 格式无法识别。请确保列名正确或使用支持的格式。")

def parse_csv(content: bytes):
    """
    解析 CSV 格式课表
    支持多种列名格式
    """
    try:
        df = pd.read_csv(io.BytesIO(content), encoding='utf-8')
    except Exception as e:
        # 尝试不同的编码
        try:
            df = pd.read_csv(io.BytesIO(content), encoding='gbk')
        except Exception as e2:
            raise ValueError(f"读取 CSV 失败: {str(e2)}")
    
    # 保存原始列名用于调试
    original_columns = df.columns.tolist()
    print(f"原始CSV列名: {original_columns}")
    
    # 标准化列名
    df.columns = [col.lower().strip() for col in df.columns]
    print(f"标准化后CSV列名: {df.columns.tolist()}")
    
    # 支持的列名映射
    possible_column_names = {
        'day': ['day', '日期', '星期', '周几', '星期几'],
        'start': ['start', '开始时间', '上课时间', '开始', '时间'],
        'end': ['end', '结束时间', '下课时间', '结束'],
        'course': ['course', '课程', '课程名称', '科目'],
        'weeks': ['weeks', '教学周', '周次', '周数']
    }
    
    # 自动检测列名映射
    detected_mapping = {}
    for field, possible_names in possible_column_names.items():
        for name in possible_names:
            if name in df.columns:
                detected_mapping[field] = name
                break
    print(f"检测到的CSV列名映射: {detected_mapping}")
    
    # 检查是否找到了所有必要的列
    required_fields = ['day', 'start', 'end']
    if all(field in detected_mapping for field in required_fields):
        schedule = []
        for _, row in df.iterrows():
            day = str(row[detected_mapping['day']]).strip()
            start = str(row[detected_mapping['start']]).strip()
            end = str(row[detected_mapping['end']]).strip()
            course = str(row.get(detected_mapping.get('course', ''), '')).strip()
            weeks_str = str(row.get(detected_mapping.get('weeks', ''), '')).strip()
            
            # 解析教学周
            weeks = []
            if weeks_str and weeks_str != 'nan':
                if '-' in weeks_str:
                    try:
                        start_week, end_week = map(int, weeks_str.split('-'))
                        weeks = list(range(start_week, end_week + 1))
                    except ValueError:
                        pass
                elif ',' in weeks_str:
                    weeks = [int(w) for w in weeks_str.split(',') if w.strip().isdigit()]
                else:
                    try:
                        weeks = [int(weeks_str)]
                    except ValueError:
                        weeks = []
            
            # 基础校验
            if day and start and end:
                # 标准化星期表示
                day_map = {
                    '1': '周一', '星期一': '周一', 'Monday': '周一',
                    '2': '周二', '星期二': '周二', 'Tuesday': '周二',
                    '3': '周三', '星期三': '周三', 'Wednesday': '周三',
                    '4': '周四', '星期四': '周四', 'Thursday': '周四',
                    '5': '周五', '星期五': '周五', 'Friday': '周五'
                }
                day = day_map.get(day, day)
                
                schedule_item = {
                    'day': day,
                    'start': start,
                    'end': end,
                    'course': course
                }
                # 如果没有明确周次，默认整个学期
                if not weeks:
                    weeks = DEFAULT_WEEKS
                schedule_item['weeks'] = weeks
                schedule.append(schedule_item)
        
        if schedule:
            return schedule
    
    raise ValueError(f"CSV 格式无法识别。请确保包含必要的列: 星期/日期, 开始时间, 结束时间")

def parse_ics(content: bytes):
    """
    解析 iCalendar (.ics) 格式课表
    返回: [{"day": "周一", "start": "10:00", "end": "12:00", "course": "课程名"}, ...]
    """
    try:
        cal = Calendar.from_ical(content)
    except Exception as e:
        raise ValueError(f"解析 ICS 失败: {str(e)}")
    
    schedule = []
    weekday_map = {
        0: '周一', 1: '周二', 2: '周三', 3: '周四', 4: '周五',
        5: '周六', 6: '周日'
    }
    
    for component in cal.walk():
        if component.name == "VEVENT":
            try:
                dtstart = component.get('dtstart')
                dtend = component.get('dtend')
                summary = component.get('summary', '')
                
                if dtstart and dtend:
                    start_dt = dtstart.dt
                    end_dt = dtend.dt
                    
                    # 获取星期几
                    weekday = weekday_map.get(start_dt.weekday(), '周一')
                    start_time = start_dt.strftime('%H:%M')
                    end_time = end_dt.strftime('%H:%M')
                    
                    schedule.append({
                        'day': weekday,
                        'start': start_time,
                        'end': end_time,
                        'course': str(summary),
                        'weeks': DEFAULT_WEEKS  # 默认整个学期
                    })
            except Exception as e:
                # 跳过无法解析的事件
                continue
    
    if not schedule:
        raise ValueError("ICS 文件中未找到有效的课程事件")
    
    return schedule

def parse_weeks_from_text(text: str):
    """
    从 '(1-2 5-14 16,三教307)' 解析教学周
    """
    weeks = set()
    matches = re.findall(r'\d+-\d+|\d+', text)
    for m in matches:
        if '-' in m:
            s, e = map(int, m.split('-'))
            weeks.update(range(s, e + 1))
        else:
            weeks.add(int(m))
    return sorted(weeks)

def parse_sufe_matrix_excel(df: pd.DataFrame):
    """
    解析上财导出的「星期 × 节次」矩阵课表
    """
    print("✅ SUFE MATRIX PARSER ACTIVATED")
    schedule = []

    # 第一行是节次时间
    time_row = df.iloc[0]

    # 节次列索引 → (start, end)
    period_time = {}
    for idx, cell in time_row.items():
        if isinstance(cell, str) and '-' in cell:
            start, end = cell.split('-')
            period_time[idx] = (start.strip(), end.strip())

    weekday_map = {
        '星期一': '周一',
        '星期二': '周二',
        '星期三': '周三',
        '星期四': '周四',
        '星期五': '周五',
        '星期六': '周六',
        '星期日': '周日',
    }

    i = 1
    while i < len(df):
        row = df.iloc[i]
        weekday_raw = str(row.iloc[0]).strip()

        if weekday_raw in weekday_map:
            day = weekday_map[weekday_raw]

            for col_idx, value in row.items():
                if col_idx not in period_time:
                    continue

                if pd.notna(value) and str(value).strip():
                    course_name = str(value).strip()

                    # 尝试读取下一行的教学周
                    weeks = []
                    if i + 1 < len(df):
                        week_info = str(df.iloc[i + 1][col_idx])
                        if week_info and week_info != 'nan':
                            weeks = parse_weeks_from_text(week_info)

                    start, end = period_time[col_idx]

                    item = {
                        'day': day,
                        'start': start,
                        'end': end,
                        'course': course_name
                    }
                    # 如果没有明确周次，默认整个学期
                    if not weeks:
                        weeks = DEFAULT_WEEKS
                    item['weeks'] = weeks

                    schedule.append(item)

        i += 2  # 跳两行（课程 + 教学周）

    if schedule:
        return schedule

    raise ValueError("未能识别上财矩阵课表")