from pydantic import BaseModel

class ScheduleItem(BaseModel):
    course: str
    weekday: int
    start: str
    end: str
    weeks: list[int]
