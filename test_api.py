import requests
import json

# 测试API并保存结果到文件
def test_api():
    url = "http://127.0.0.1:8000/api/places/recommend"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    data = {
        "coords": [[31.2048, 121.4500], [31.2222, 121.4375]],
        "cuisine": "咖啡",
        "radius": 2000
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        
        # 解析JSON响应
        result = response.json()
        
        # 将结果保存到文件
        with open("api_result.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"请求成功！状态码: {response.status_code}")
        print("结果已保存到 api_result.json 文件中")
        
        # 直接打印结果（确保正确编码）
        print("\n直接打印结果（UTF-8）:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        if hasattr(e, 'response') and e.response:
            try:
                error_data = e.response.json()
                print(f"错误详情: {json.dumps(error_data, ensure_ascii=False)}")
            except:
                print(f"响应内容: {e.response.text}")

if __name__ == "__main__":
    test_api()