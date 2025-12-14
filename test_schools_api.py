import requests

# 测试学校列表API
print("测试学校列表API...")
try:
    response = requests.get("http://localhost:8001/api/schools")
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"学校数量: {len(data)}")
        for school in data[:5]:  # 只显示前5个
            print(f"ID: {school['id']}, 名称: {school['name']}")
    else:
        print(f"请求失败: {response.text}")
except Exception as e:
    print(f"发生错误: {e}")

print("\n" + "="*50 + "\n")

# 测试单个学校API
print("测试单个学校API...")
try:
    school_id = 1  # 假设第一个学校的ID是1
    response = requests.get(f"http://localhost:8001/api/schools/{school_id}")
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"学校详情: {data}")
    else:
        print(f"请求失败: {response.text}")
except Exception as e:
    print(f"发生错误: {e}")
