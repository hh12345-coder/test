import requests
import json

# 直接测试time_blocks的初始化和课程标记逻辑
def test_time_blocks_direct():
    # 定义简单的测试数据
    test_data = {
        "schedules": [
            [
                # 第1周周一 08:00-09:00 有课
                {"day": "周一", "start": "08:00", "end": "09:00", "weeks": [1]},
                # 第1周周三 14:00-15:00 有课
                {"day": "周三", "start": "14:00", "end": "15:00", "weeks": [1]}
            ]
        ],
        "exclude_times": [],
        "week": 1,
        "ideal_time": "15:00"
    }
    
    # 发送请求
    response = requests.post(
        "http://localhost:8001/api/schedule/free_times",
        headers={"Content-Type": "application/json"},
        data=json.dumps(test_data)
    )
    
    # 打印响应
    print(f"响应状态码: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"空闲时间数量: {len(result['free_times'])}")
        print(f"推荐时间: {result['recommended_time']}")
        print(f"当前周: {result['current_week']}")
        print(f"总空闲时间段: {result['total_free_slots']}")
        
        # 打印所有空闲时间
        print("\n所有空闲时间:")
        for free_time in result['free_times']:
            print(f"  {free_time['day']} {free_time['start']}-{free_time['end']} ({free_time['duration_min']}分钟)")
        
        # 验证特定的空闲时间
        print("\n验证特定的空闲时间:")
        
        # 验证周一上午是否有课（08:00-09:00不应该空闲）
        monday_morning_free = any(ft['day'] == '周一' and ft['start'] == '08:00' for ft in result['free_times'])
        print(f"周一 08:00-09:00 是否空闲: {'是' if monday_morning_free else '否'} (预期: 否)")
        
        # 验证周一09:00-22:00是否空闲
        monday_after_free = any(ft['day'] == '周一' and ft['start'] == '09:00' for ft in result['free_times'])
        print(f"周一 09:00-22:00 是否空闲: {'是' if monday_after_free else '否'} (预期: 是)")
        
        # 验证周三下午是否有课（14:00-15:00不应该空闲）
        wednesday_afternoon_free = any(ft['day'] == '周三' and ft['start'] == '14:00' for ft in result['free_times'])
        print(f"周三 14:00-15:00 是否空闲: {'是' if wednesday_afternoon_free else '否'} (预期: 否)")
        
        # 验证周三15:00-22:00是否空闲
        wednesday_evening_free = any(ft['day'] == '周三' and ft['start'] == '15:00' for ft in result['free_times'])
        print(f"周三 15:00-22:00 是否空闲: {'是' if wednesday_evening_free else '否'} (预期: 是)")
        
        # 验证周二全天是否空闲
        tuesday_all_day_free = any(ft['day'] == '周二' and ft['start'] == '08:00' and ft['end'] == '22:00' for ft in result['free_times'])
        print(f"周二 08:00-22:00 是否空闲: {'是' if tuesday_all_day_free else '否'} (预期: 是)")
    else:
        print(f"请求失败: {response.text}")

if __name__ == "__main__":
    test_time_blocks_direct()