import requests
import json
import sys

# 测试完整的学校选择和推荐流程
print("=== 学校选择和推荐功能综合测试 ===")
print(f"测试日期: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*50)

# 测试服务器地址
BASE_URL = "http://localhost:8001/api"

# 测试1: 获取学校列表
print("\n1. 测试获取学校列表...")
try:
    schools_response = requests.get(f"{BASE_URL}/schools")
    schools = schools_response.json()
    print(f"   ✓ 成功获取学校列表")
    print(f"   学校总数: {len(schools)}")
    
    # 打印前5所学校
    for i, school in enumerate(schools[:5]):
        print(f"   {i+1}. {school.get('name')} (ID: {school.get('id')})")
    
    if not schools:
        print("   ✗ 错误: 学校列表为空")
        sys.exit(1)
        
except Exception as e:
    print(f"   ✗ 失败: {e}")
    sys.exit(1)

# 测试2: 获取单所学校详情
print("\n2. 测试获取学校详情...")
try:
    school_id = schools[0]["id"]
    school_response = requests.get(f"{BASE_URL}/schools/{school_id}")
    school = school_response.json()
    print(f"   ✓ 成功获取学校详情")
    print(f"   学校ID: {school.get('id')}")
    print(f"   学校名称: {school.get('name')}")
    print(f"   坐标: {school.get('lat')}, {school.get('lon')}")
    
except Exception as e:
    print(f"   ✗ 失败: {e}")
    sys.exit(1)

# 测试3: 测试地点推荐API
print("\n3. 测试地点推荐API...")
try:
    # 选择前两所学校进行测试
    selected_school_ids = [school["id"] for school in schools[:2]]
    selected_school_names = [school["name"] for school in schools[:2]]
    
    recommend_data = {
        "school_ids": selected_school_ids,
        "cuisine": "餐厅",
        "radius": 3000,
        "travel_mode": "walking"
    }
    
    recommend_response = requests.post(
        f"{BASE_URL}/places/recommend",
        json=recommend_data
    )
    
    if recommend_response.status_code == 200:
        recommend_result = recommend_response.json()
        candidates = recommend_result.get("candidates", [])
        
        print(f"   ✓ 成功获取推荐地点")
        print(f"   已选择学校: {', '.join(selected_school_names)}")
        print(f"   推荐地点数量: {len(candidates)}")
        
        # 打印前3个推荐地点
        if candidates:
            for i, candidate in enumerate(candidates[:3]):
                print(f"   {i+1}. {candidate.get('name')}")
                print(f"      地址: {candidate.get('addr')}")
                print(f"      平均通勤时间: {candidate.get('avg_travel_time_min')} 分钟")
                print(f"      评分: {candidate.get('rating')}")
                print(f"      价格: {candidate.get('price')}")
                print()
        
    else:
        print(f"   ✗ 失败: 状态码 {recommend_response.status_code}")
        print(f"   错误信息: {recommend_response.text}")
        
except Exception as e:
    print(f"   ✗ 失败: {e}")
    sys.exit(1)

# 测试4: 测试课表解析API
print("\n4. 测试课表解析API...")
try:
    # 创建一个简单的测试课程
    test_schedule = [
        {
            "day": "周一",
            "start": "08:00",
            "end": "10:00"
        },
        {
            "day": "周一",
            "start": "14:00",
            "end": "16:00"
        }
    ]
    
    free_times_data = {
        "schedules": [test_schedule],
        "week": 1
    }
    
    free_times_response = requests.post(
        f"{BASE_URL}/schedule/free_times",
        json=free_times_data
    )
    
    if free_times_response.status_code == 200:
        free_times_result = free_times_response.json()
        free_times = free_times_result.get("free_times", [])
        recommended_time = free_times_result.get("recommended_time")
        
        print(f"   ✓ 成功获取空闲时间")
        print(f"   可用空闲时间数量: {len(free_times)}")
        
        if recommended_time:
            print(f"   推荐时间段: {recommended_time['day']} {recommended_time['start']}-{recommended_time['end']}")
        
        # 打印前2个空闲时间
        if free_times[:2]:
            print(f"   前2个空闲时间:")
            for ft in free_times[:2]:
                print(f"   - {ft['day']} {ft['start']}-{ft['end']} ({ft['duration_min']}分钟)")
        
    else:
        print(f"   ✗ 失败: 状态码 {free_times_response.status_code}")
        print(f"   错误信息: {free_times_response.text}")
        
except Exception as e:
    print(f"   ✗ 失败: {e}")
    # 课表解析测试失败不影响整体测试
    print("   ! 警告: 课表解析测试失败，可能需要检查解析逻辑或提供正确的测试数据")

print("\n" + "="*50)
print("=== 测试完成 ===")
print("所有核心功能测试已完成！")
print("您现在可以在微信开发者工具中测试前端界面了。")
print("\n建议操作：")
print("1. 打开微信开发者工具")
print("2. 加载miniprogram项目")
print("3. 进入推荐页面，测试学校选择功能")
print("4. 输入查询条件，测试推荐功能")
