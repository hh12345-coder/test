import pandas as pd
import io
import sys
import os

# 将项目根目录添加到Python路径
sys.path.append(os.path.abspath('.'))

from app.utils.schedule_parser import parse_schedule_file

def test_excel_with_uppercase_columns():
    """测试使用大写列名的Excel文件"""
    # 创建一个带有大写列名的DataFrame
    data = {
        'Day': ['周一', '周二', '周三'],
        'Start': ['09:00', '10:30', '14:00'],
        'End': ['10:45', '12:15', '15:45'],
        'Course': ['高等数学', '大学英语', '计算机科学'],
        'Weeks': ['1-8', '1-16', '1-16']
    }
    df = pd.DataFrame(data)
    
    # 将DataFrame保存到Excel
    excel_buffer = io.BytesIO()
    df.to_excel(excel_buffer, index=False, engine='openpyxl')
    excel_buffer.seek(0)
    
    try:
        # 测试解析
        result = parse_schedule_file('test.xlsx', excel_buffer.getvalue())
        print("✓ Excel测试通过！")
        print(f"解析结果: {result}")
        return True
    except Exception as e:
        print(f"✗ Excel测试失败: {e}")
        return False

def test_csv_with_uppercase_columns():
    """测试使用大写列名的CSV文件"""
    # 创建CSV内容
    csv_content = """Day,Start,End,Course,Weeks
周一,09:00,10:45,高等数学,1-8
周二,10:30,12:15,大学英语,1-16
周三,14:00,15:45,计算机科学,1-16
"""
    csv_bytes = csv_content.encode('utf-8')
    
    try:
        # 测试解析
        result = parse_schedule_file('test.csv', csv_bytes)
        print("✓ CSV测试通过！")
        print(f"解析结果: {result}")
        return True
    except Exception as e:
        print(f"✗ CSV测试失败: {e}")
        return False

def test_excel_with_chinese_columns():
    """测试使用中文列名的Excel文件"""
    # 创建一个带有中文列名的DataFrame
    data = {
        '星期': ['周一', '周二', '周三'],
        '开始时间': ['09:00', '10:30', '14:00'],
        '结束时间': ['10:45', '12:15', '15:45'],
        '课程': ['高等数学', '大学英语', '计算机科学'],
        '教学周': ['1-8', '1-16', '1-16']
    }
    df = pd.DataFrame(data)
    
    # 将DataFrame保存到Excel
    excel_buffer = io.BytesIO()
    df.to_excel(excel_buffer, index=False, engine='openpyxl')
    excel_buffer.seek(0)
    
    try:
        # 测试解析
        result = parse_schedule_file('test_chinese.xlsx', excel_buffer.getvalue())
        print("✓ 中文列名Excel测试通过！")
        print(f"解析结果: {result}")
        return True
    except Exception as e:
        print(f"✗ 中文列名Excel测试失败: {e}")
        return False

if __name__ == "__main__":
    print("测试列名解析修复...")
    print("=" * 50)
    
    # 运行所有测试
    test1 = test_excel_with_uppercase_columns()
    print()
    test2 = test_csv_with_uppercase_columns()
    print()
    test3 = test_excel_with_chinese_columns()
    print()
    
    # 总结
    if all([test1, test2, test3]):
        print("🎉 所有测试通过！修复有效。")
    else:
        print("❌ 部分测试失败，需要进一步调试。")
