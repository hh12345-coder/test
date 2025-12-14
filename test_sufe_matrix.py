import pandas as pd
import io
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.utils.schedule_parser import parse_sufe_matrix_excel, parse_schedule_file, parse_excel

def test_parse_sufe_matrix_excel():
    """
    测试上财矩阵型课表解析器
    """
    print("测试上财矩阵型课表解析...")
    
    # 创建模拟的上财矩阵型课表数据
    data = {
        0: ['星期节次', '第一节 8:00-8:45', '第二节 8:55-9:40', '第三节 10:00-10:45', '第四节 10:55-11:40', '第五节 14:00-14:45', '第六节 14:55-15:40'],
        1: ['星期一', '李婷 概率论', '', '王刚 数据结构', '', '', ''],
        2: ['', '(1-2 5-14 16,三教307)', '', '(3-12,一教101)', '', '', ''],
        3: ['星期二', '', '张教授 高等数学', '', '', '', ''],
        4: ['', '', '(1-16,二教202)', '', '', '', ''],
        5: ['星期三', '', '', '', '王老师 英语', '', ''],
        6: ['', '', '', '', '(1-8,三教303)', '', ''],
    }
    
    # 创建DataFrame
    df = pd.DataFrame.from_dict(data, orient='index')
    
    # 测试解析
    try:
        result = parse_sufe_matrix_excel(df)
        print("解析成功！")
        print(f"共解析出 {len(result)} 门课程")
        for i, course in enumerate(result):
            print(f"\n课程 {i+1}:")
            print(f"  星期: {course['day']}")
            print(f"  开始时间: {course['start']}")
            print(f"  结束时间: {course['end']}")
            print(f"  课程名: {course['course']}")
            if 'weeks' in course:
                print(f"  教学周: {course['weeks']}")
        return True
    except Exception as e:
        print(f"解析失败: {e}")
        print("DataFrame结构:")
        print(df)
        print("DataFrame列名:")
        print(df.columns)
        return False

def test_parse_excel_with_matrix():
    """
    测试通过parse_excel函数解析上财矩阵型Excel
    """
    print("\n测试通过parse_excel函数解析上财矩阵型Excel...")
    
    # 创建模拟的上财矩阵型课表数据
    data = {
        0: ['星期节次', '第一节 8:00-8:45', '第二节 8:55-9:40', '第三节 10:00-10:45', '第四节 10:55-11:40', '第五节 14:00-14:45', '第六节 14:55-15:40'],
        1: ['星期一', '李婷 概率论', '', '王刚 数据结构', '', '', ''],
        2: ['', '(1-2 5-14 16,三教307)', '', '(3-12,一教101)', '', '', ''],
        3: ['星期二', '', '张教授 高等数学', '', '', '', ''],
        4: ['', '', '(1-16,二教202)', '', '', '', ''],
        5: ['星期三', '', '', '', '王老师 英语', '', ''],
        6: ['', '', '', '', '(1-8,三教303)', '', ''],
    }
    
    # 创建DataFrame
    df = pd.DataFrame.from_dict(data, orient='index')
    
    # 将DataFrame保存为Excel文件
    excel_buffer = io.BytesIO()
    df.to_excel(excel_buffer, index=False, header=False)
    excel_buffer.seek(0)
    
    # 测试解析
    try:
        result = parse_excel(excel_buffer.getvalue())
        print("解析成功！")
        print(f"共解析出 {len(result)} 门课程")
        for i, course in enumerate(result):
            print(f"\n课程 {i+1}:")
            print(f"  星期: {course['day']}")
            print(f"  开始时间: {course['start']}")
            print(f"  结束时间: {course['end']}")
            print(f"  课程名: {course['course']}")
            if 'weeks' in course:
                print(f"  教学周: {course['weeks']}")
        return True
    except Exception as e:
        print(f"解析失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_parse_schedule_file_with_matrix():
    """
    测试通过parse_schedule_file函数解析上财矩阵型Excel
    """
    print("\n测试通过parse_schedule_file函数解析上财矩阵型Excel...")
    
    # 创建模拟的上财矩阵型课表数据
    data = {
        0: ['星期节次', '第一节 8:00-8:45', '第二节 8:55-9:40', '第三节 10:00-10:45', '第四节 10:55-11:40', '第五节 14:00-14:45', '第六节 14:55-15:40'],
        1: ['星期一', '李婷 概率论', '', '王刚 数据结构', '', '', ''],
        2: ['', '(1-2 5-14 16,三教307)', '', '(3-12,一教101)', '', '', ''],
        3: ['星期二', '', '张教授 高等数学', '', '', '', ''],
        4: ['', '', '(1-16,二教202)', '', '', '', ''],
        5: ['星期三', '', '', '', '王老师 英语', '', ''],
        6: ['', '', '', '', '(1-8,三教303)', '', ''],
    }
    
    # 创建DataFrame
    df = pd.DataFrame.from_dict(data, orient='index')
    
    # 将DataFrame保存为Excel文件
    excel_buffer = io.BytesIO()
    df.to_excel(excel_buffer, index=False, header=False)
    excel_buffer.seek(0)
    
    # 测试解析
    try:
        result = parse_schedule_file('test_sufe.xlsx', excel_buffer.getvalue())
        print("解析成功！")
        print(f"共解析出 {len(result)} 门课程")
        for i, course in enumerate(result):
            print(f"\n课程 {i+1}:")
            print(f"  星期: {course['day']}")
            print(f"  开始时间: {course['start']}")
            print(f"  结束时间: {course['end']}")
            print(f"  课程名: {course['course']}")
            if 'weeks' in course:
                print(f"  教学周: {course['weeks']}")
        return True
    except Exception as e:
        print(f"解析失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=== 上财矩阵型课表解析器测试 ===\n")
    
    # 测试直接调用parse_sufe_matrix_excel函数
    test1_passed = test_parse_sufe_matrix_excel()
    
    # 测试通过parse_excel函数解析
    test2_passed = test_parse_excel_with_matrix()
    
    # 测试通过parse_schedule_file函数解析
    test3_passed = test_parse_schedule_file_with_matrix()
    
    print("\n=== 测试结果 ===")
    print(f"直接解析测试: {'通过' if test1_passed else '失败'}")
    print(f"parse_excel函数测试: {'通过' if test2_passed else '失败'}")
    print(f"parse_schedule_file函数测试: {'通过' if test3_passed else '失败'}")
    
    if test1_passed and test2_passed and test3_passed:
        print("\n✅ 所有测试通过！上财矩阵型课表解析器工作正常。")
        sys.exit(0)
    else:
        print("\n❌ 部分测试失败！")
        sys.exit(1)