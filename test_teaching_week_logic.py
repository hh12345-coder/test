import requests
import json

# 测试不同教学周下的空闲时间计算

def test_different_teaching_weeks():
    # 定义测试数据
    test_data = {
        "schedules": [
            [
                # 高等数学：第1-8周 周一 08:00-09:40
                {"day": "周一", "start": "08:00", "end": "09:40", "weeks": [1, 2, 3, 4, 5, 6, 7, 8]},
                # 大学英语：第1-16周 周三 14:00-15:40
                {"day": "周三", "start": "14:00", "end": "15:40", "weeks": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]},
                # 程序设计：所有周 周五 10:00-11:40
                {"day": "周五", "start": "10:00", "end": "11:40"}
            ]
        ],
        "exclude_times": [],
        "ideal_time": "15:00"
    }
    
    # 测试不同的教学周
    test_weeks = [1, 8, 9, 16]
    
    for week in test_weeks:
        test_data["week"] = week
        print(f"\n\n测试第{week}周空闲时间：")
        print("Test Data:", json.dumps(test_data, indent=2, ensure_ascii=False))
        
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
            
            # 检查周一上午是否有课
            monday_morning_free = True
            for free_time in result['free_times']:
                if free_time['day'] == '周一' and free_time['start'] == '08:00':
                    monday_morning_free = True
                    break
                elif free_time['day'] == '周一' and free_time['start'] > '08:00':
                    monday_morning_free = False
                    break
            
            print(f"周一上午是否空闲: {'是' if monday_morning_free else '否'}")
            
            # 检查周三下午是否有课
            wednesday_afternoon_free = True
            for free_time in result['free_times']:
                if free_time['day'] == '周三' and free_time['start'] == '14:00':
                    wednesday_afternoon_free = True
                    break
                elif free_time['day'] == '周三' and free_time['start'] > '14:00':
                    wednesday_afternoon_free = False
                    break
            
            print(f"周三下午是否空闲: {'是' if wednesday_afternoon_free else '否'}")
            
            # 检查周五上午是否有课
            friday_morning_free = True
            for free_time in result['free_times']:
                if free_time['day'] == '周五' and free_time['start'] == '10:00':
                    friday_morning_free = True
                    break
                elif free_time['day'] == '周五' and free_time['start'] > '10:00':
                    friday_morning_free = False
                    break
            
            print(f"周五上午是否空闲: {'是' if friday_morning_free else '否'}")
        else:
            print(f"请求失败: {response.text}")

if __name__ == "__main__":
    test_different_teaching_weeks()