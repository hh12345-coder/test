import io
import pandas as pd
from icalendar import Calendar

def parse_schedule_file(filename: str, content: bytes):
    if filename.endswith('.xlsx'):
        df = pd.read_excel(io.BytesIO(content))
        # 简单示例：期望列名 Day/Start/End
        schedule = df[['Day','Start','End']].to_dict(orient='records')
        return schedule
    elif filename.endswith('.ics'):
        cal = Calendar.from_ical(content)
        schedule = []
        for event in cal.walk('VEVENT'):
            day = event.get('DTSTART').dt.strftime('%A')
            start = event.get('DTSTART').dt.strftime('%H:%M')
            end = event.get('DTEND').dt.strftime('%H:%M')
            schedule.append({'day': day, 'start': start, 'end': end})
        return schedule
    else:
        raise ValueError("不支持的文件格式")