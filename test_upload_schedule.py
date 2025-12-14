import requests
import os

# 测试课表上传API
print("测试课表上传API...")

# 准备测试文件
test_file_path = "test_schedule.xlsx"
if not os.path.exists(test_file_path):
    print(f"测试文件 {test_file_path} 不存在，正在使用其他测试文件...")
    # 尝试其他可能的测试文件
    possible_files = ["test_course_schedule.xlsx", "example_schedule.xlsx", "test_schedule_valid.xlsx"]
    for file in possible_files:
        if os.path.exists(file):
            test_file_path = file
            break
    else:
        print("没有找到可用的Excel测试文件")
        exit(1)

print(f"使用测试文件: {test_file_path}")

# 上传文件
try:
    with open(test_file_path, "rb") as f:
        files = {"file": (test_file_path, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        # 由于需要认证，我们先尝试不使用用户认证的方式（如果路由支持）
        # 如果需要认证，可以添加token到headers
        headers = {}
        response = requests.post("http://localhost:8001/api/schedule/upload", files=files, headers=headers)
        print(f"状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
except Exception as e:
    print(f"发生错误: {e}")
