import requests
import json
import os
import pandas as pd

# 全面测试脚本：测试上传课程表和获取空闲时间的完整功能

# 配置
BASE_URL = 'http://localhost:8001'
USER_ID = 123456
TEST_FILE_PATH = 'test_course_schedule.xlsx'

# 创建测试课程表

def create_test_course_schedule():
    # 创建一个简单的课程表DataFrame
    data = {
        '课程名称': ['高等数学', '大学英语', '程序设计'],
        '星期': ['周一', 'Wednesday', '3'],  # 测试不同格式的星期值
        '开始时间': ['08:00', '14:00', '10:30'],
        '结束时间': ['09:40', '15:40', '12:10'],
        '教学周': ['1-8', '1-16', '']  # 测试不同格式的教学周，包括空值
    }
    
    df = pd.DataFrame(data)
    df.to_excel(TEST_FILE_PATH, index=False)
    print(f"已创建测试课程表: {TEST_FILE_PATH}")
    return TEST_FILE_PATH

# 测试上传课程表

def test_upload_course_schedule(file_path):
    url = f'{BASE_URL}/api/schedule/upload'
    files = {'file': open(file_path, 'rb')}
    data = {'user_id': USER_ID}
    
    try:
        response = requests.post(url, files=files, data=data)
        print(f"\n测试上传课程表:")
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"上传课程表失败: {e}")
        return False
    finally:
        files['file'].close()

# 测试获取我的课程表

def test_get_my_schedule():
    url = f'{BASE_URL}/api/schedule/my'
    params = {'user_id': USER_ID}
    
    try:
        response = requests.get(url, params=params)
        print(f"\n测试获取我的课程表:")
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            schedules = response.json()['schedules']
            print(f"课程数量: {len(schedules)}")
            for s in schedules[:3]:  # 只显示前3个课程
                print(f"  - {s.get('course', '未命名课程')}: {s['day']} {s['start']}-{s['end']}, 教学周: {s['weeks']}")
        return response.status_code == 200
    except Exception as e:
        print(f"获取课程表失败: {e}")
        return False

# 测试获取空闲时间

def test_get_free_times(week):
    url = f'{BASE_URL}/api/schedule/free_times'
    
    # 获取我的课程表用于请求空闲时间
    my_schedule_url = f'{BASE_URL}/api/schedule/my'
    params = {'user_id': USER_ID}
    my_schedule = requests.get(my_schedule_url, params=params).json()
    
    # 构造请求数据
    data = {
        'schedules': [my_schedule['schedules']],
        'week': week,
        'excluded_times': []
    }
    
    try:
        response = requests.post(url, json=data)
        print(f"\n测试获取第{week}周空闲时间:")
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            free_times = result['free_times']
            print(f"空闲时间数量: {len(free_times)}")
            print(f"推荐时间: {result['recommended_time']}")
            print(f"当前周: {result['current_week']}")
            print(f"总空闲时间段: {result['total_free_slots']}")
            for ft in free_times:
                print(f"  {ft['day']}: {ft['start']}-{ft['end']} ({ft['duration_min']}分钟)")
        return response.status_code == 200
    except Exception as e:
        print(f"获取空闲时间失败: {e}")
        return False

# 清理测试文件

def cleanup_test_file(file_path):
    if os.path.exists(file_path):
        os.remove(file_path)
        print(f"\n已清理测试文件: {file_path}")

if __name__ == "__main__":
    print("开始全面测试...")
    
    # 创建测试课程表
    test_file = create_test_course_schedule()
    
    try:
        # 测试上传课程表
        upload_success = test_upload_course_schedule(test_file)
        
        if upload_success:
            # 测试获取我的课程表
            get_schedule_success = test_get_my_schedule()
            
            if get_schedule_success:
                # 测试获取第1周空闲时间（应该有课程）
                test_get_free_times(1)
                
                # 测试获取第9周空闲时间（高数应该不显示，因为只在1-8周）
                test_get_free_times(9)
    finally:
        # 清理测试文件
        cleanup_test_file(test_file)
        
    print("\n测试完成！")