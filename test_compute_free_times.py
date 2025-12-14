# 直接测试compute_free_times函数的核心逻辑
import sys
import os
import asyncio

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.routers.schedule import compute_free_times
from app.routers.schedule import ScheduleItem, ExcludedTimeSlot, FreeTimeRequest

# 测试不同星期格式和教学周的课程
test_courses = [
    # 测试中文星期和范围教学周
    ScheduleItem(day="周一", start="08:00", end="09:40", weeks=[1,2,3,4,5,6,7,8]),
    
    # 测试英文星期和完整教学周
    ScheduleItem(day="Wednesday", start="14:00", end="15:40", weeks=[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]),
    
    # 测试数字星期和空教学周（应该默认每周都有）
    ScheduleItem(day="3", start="10:30", end="12:10", weeks=[]),
    
    # 测试空教学周（应该默认每周都有）
    ScheduleItem(day="周四", start="16:00", end="17:40", weeks=[]),
    
    # 测试只在第9周及以后有课的课程
    ScheduleItem(day="周五", start="09:50", end="11:30", weeks=[9,10,11,12,13,14,15,16])
]

# 测试第1周的空闲时间
async def test_week_1():
    print("\n=== 测试第1周空闲时间 ===")
    
    # 手动排除的时间段（测试功能）
    excluded_times = [
        ExcludedTimeSlot(day="周一", start="16:00", end="18:00")
    ]
    
    # 创建FreeTimeRequest对象
    req = FreeTimeRequest(
        schedules=[test_courses],  # 单用户的课程列表
        week=1,
        excluded_times=excluded_times
    )
    
    # 调用计算空闲时间的函数（使用None作为db参数）
    result = await compute_free_times(req, db=None)
    
    # 打印结果
    print(f"当前周: {result['current_week']}")
    print(f"总空闲时段数: {result['total_free_slots']}")
    print(f"推荐时间: {result['recommended_time']}")
    
    print("\n所有空闲时间：")
    for time_slot in result['free_times']:
        print(f"  {time_slot['day']} {time_slot['start']}-{time_slot['end']} ({time_slot['duration_min']}分钟)")

# 测试第9周的空闲时间
async def test_week_9():
    print("\n=== 测试第9周空闲时间 ===")
    
    # 创建FreeTimeRequest对象
    req = FreeTimeRequest(
        schedules=[test_courses],  # 单用户的课程列表
        week=9
    )
    
    # 调用计算空闲时间的函数
    result = await compute_free_times(req, db=None)
    
    # 打印结果
    print(f"当前周: {result['current_week']}")
    print(f"总空闲时段数: {result['total_free_slots']}")
    print(f"推荐时间: {result['recommended_time']}")
    
    print("\n所有空闲时间：")
    for time_slot in result['free_times']:
        print(f"  {time_slot['day']} {time_slot['start']}-{time_slot['end']} ({time_slot['duration_min']}分钟)")

# 测试第10周的空闲时间（应该和第9周一样）
async def test_week_10():
    print("\n=== 测试第10周空闲时间 ===")
    
    # 创建FreeTimeRequest对象
    req = FreeTimeRequest(
        schedules=[test_courses],  # 单用户的课程列表
        week=10
    )
    
    # 调用计算空闲时间的函数
    result = await compute_free_times(req, db=None)
    
    # 打印结果
    print(f"当前周: {result['current_week']}")
    print(f"总空闲时段数: {result['total_free_slots']}")
    print(f"推荐时间: {result['recommended_time']}")
    
    print("\n所有空闲时间：")
    for time_slot in result['free_times']:
        print(f"  {time_slot['day']} {time_slot['start']}-{time_slot['end']} ({time_slot['duration_min']}分钟)")

# 测试无课程的情况
async def test_no_courses():
    print("\n=== 测试无课程的情况 ===")
    
    # 创建FreeTimeRequest对象
    req = FreeTimeRequest(
        schedules=[[]],  # 无课程
        week=1
    )
    
    # 调用计算空闲时间的函数
    result = await compute_free_times(req, db=None)
    
    # 打印结果
    print(f"当前周: {result['current_week']}")
    print(f"总空闲时段数: {result['total_free_slots']}")
    print(f"推荐时间: {result['recommended_time']}")
    
    print("\n所有空闲时间：")
    for time_slot in result['free_times']:
        print(f"  {time_slot['day']} {time_slot['start']}-{time_slot['end']} ({time_slot['duration_min']}分钟)")

async def run_all_tests():
    await test_week_1()
    await test_week_9()
    await test_week_10()
    await test_no_courses()

if __name__ == "__main__":
    print("开始测试compute_free_times函数...")
    
    # 使用asyncio运行所有测试
    asyncio.run(run_all_tests())
    
    print("\n测试完成！")