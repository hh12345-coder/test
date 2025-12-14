import sqlite3
import os

# 数据库清洗脚本：将没有教学周信息的旧课程默认设置为每周都有（1-16周）

def cleanup_schedule_data():
    # 获取数据库路径
    db_path = os.path.join(os.path.dirname(__file__), 'school_meal.db')
    
    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        return
    
    try:
        # 连接到SQLite数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查看当前schedules表结构
        cursor.execute("PRAGMA table_info(schedules)")
        columns = cursor.fetchall()
        print("当前schedules表结构:")
        for column in columns:
            print(f"  {column[1]} ({column[2]})")
        
        # 查看旧数据的情况
        cursor.execute("SELECT COUNT(*) FROM schedules WHERE weeks IS NULL OR weeks = ''")
        null_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM schedules")
        total_count = cursor.fetchone()[0]
        
        print(f"\n数据库中共有 {total_count} 条课程记录")
        print(f"其中 {null_count} 条记录没有教学周信息")
        
        # 执行清洗操作：将没有教学周信息的记录设置为1-16周
        if null_count > 0:
            cursor.execute("UPDATE schedules SET weeks = '1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16' WHERE weeks IS NULL OR weeks = ''")
            conn.commit()
            print(f"已成功更新 {cursor.rowcount} 条记录")
        
        # 验证清洗结果
        cursor.execute("SELECT COUNT(*) FROM schedules WHERE weeks IS NULL OR weeks = ''")
        remaining_nulls = cursor.fetchone()[0]
        print(f"清洗后剩余 {remaining_nulls} 条记录没有教学周信息")
        
        # 检查星期格式
        cursor.execute("SELECT DISTINCT day FROM schedules LIMIT 10")
        days = cursor.fetchall()
        print("\n当前课程记录中的星期格式:")
        for day in days:
            print(f"  - {day[0]}")
        
    except Exception as e:
        print(f"清洗过程中发生错误: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    cleanup_schedule_data()