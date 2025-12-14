import requests
import json

# 测试不同教学周的过滤功能
def test_free_times_with_different_weeks():
    # 定义测试数据：包含第一周和第二周的课程
    test_data = {
        "schedules": [
            [
                # 第一周的课程
                {"day": "周一", "start": "08:00", "end": "09:30", "weeks": [1]},
                {"day": "周三", "start": "14:00", "end": "15:30", "weeks": [1]},
                # 第二周的课程
                {"day": "周二", "start": "10:00", "end": "11:30", "weeks": [2]},
                {"day": "周四", "start": "16:00", "end": "17:30", "weeks": [2]}
            ]
        ],
        "exclude_times": [],
        "ideal_time": "15:00"
    }
    
    # 测试第1周
    print("\n=== 测试第1周 ===")
    test_data["week"] = 1
    response = requests.post(
        "http://localhost:8001/api/schedule/free_times",
        headers={"Content-Type": "application/json"},
        data=json.dumps(test_data)
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"当前周: {result['current_week']}")
        print("空闲时间:")
        for free_time in result["free_times"]:
            print(f"  {free_time['day']} {free_time['start']}-{free_time['end']} ({free_time['duration_min']}分钟)")
    else:
        print(f"错误: {response.json()}")
    
    # 测试第2周
    print("\n=== 测试第2周 ===")
    test_data["week"] = 2
    response = requests.post(
        "http://localhost:8001/api/schedule/free_times",
        headers={"Content-Type": "application/json"},
        data=json.dumps(test_data)
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"当前周: {result['current_week']}")
        print("空闲时间:")
        for free_time in result["free_times"]:
            print(f"  {free_time['day']} {free_time['start']}-{free_time['end']} ({free_time['duration_min']}分钟)")
    else:
        print(f"错误: {response.json()}")

if __name__ == "__main__":
    test_free_times_with_different_weeks()