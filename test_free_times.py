import requests
import json

# 测试compute_free_times API是否能正确处理教学周信息

def test_free_times_with_weeks():
    # 定义测试数据
    test_data = {
        "schedules": [
            [
                # 第一周的课程（当前周） - 应该被考虑
                {"day": "周一", "start": "08:00", "end": "09:30", "weeks": [1]},
                {"day": "周三", "start": "14:00", "end": "15:30", "weeks": [1]}
            ]
        ],
        "exclude_times": [],
        "week": 1,  # 当前是第1周
        "ideal_time": "15:00"
    }
    
    print("Test Data:", json.dumps(test_data, indent=2, ensure_ascii=False))
    
    # 发送请求
    response = requests.post(
        "http://localhost:8001/api/schedule/free_times",
        headers={"Content-Type": "application/json"},
        data=json.dumps(test_data)
    )
    
    # 打印响应
    print("Response Status Code:", response.status_code)
    if response.status_code == 200:
        result = response.json()
        print("Free Times Count:", len(result["free_times"]))
        for i, free_time in enumerate(result["free_times"]):
            print(f"Free Time {i+1}: {free_time['day']} {free_time['start']}-{free_time['end']} ({free_time['duration_min']}分钟)")
        print("Current Week:", result["current_week"])
    else:
        print("Error:", response.json())

# 测试没有教学周的情况
def test_free_times_without_weeks():
    # 定义测试数据
    test_data = {
        "schedules": [
            [
                # 没有教学周的课程 - 应该总是被考虑
                {"day": "周一", "start": "08:00", "end": "09:30"},
                {"day": "周三", "start": "14:00", "end": "15:30"}
            ]
        ],
        "exclude_times": [],
        "week": 1,  # 当前是第1周
        "ideal_time": "15:00"
    }
    
    print("\n\nTest Data (without weeks):", json.dumps(test_data, indent=2, ensure_ascii=False))
    
    # 发送请求
    response = requests.post(
        "http://localhost:8001/api/schedule/free_times",
        headers={"Content-Type": "application/json"},
        data=json.dumps(test_data)
    )
    
    # 打印响应
    print("Response Status Code:", response.status_code)
    if response.status_code == 200:
        result = response.json()
        print("Free Times Count:", len(result["free_times"]))
        for i, free_time in enumerate(result["free_times"]):
            print(f"Free Time {i+1}: {free_time['day']} {free_time['start']}-{free_time['end']} ({free_time['duration_min']}分钟)")
        print("Current Week:", result["current_week"])
    else:
        print("Error:", response.json())

if __name__ == "__main__":
    test_free_times_with_weeks()
    test_free_times_without_weeks()