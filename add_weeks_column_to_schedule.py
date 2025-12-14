import sqlite3
import os

# 为schedules表添加weeks列

def add_weeks_column():
    # 获取数据库路径
    db_path = os.path.join(os.path.dirname(__file__), 'school_meal.db')
    
    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        return
    
    try:
        # 连接到SQLite数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查schedules表是否已经有weeks列
        cursor.execute("PRAGMA table_info(schedules)")
        columns = cursor.fetchall()
        has_weeks_column = any(column[1] == 'weeks' for column in columns)
        
        if not has_weeks_column:
            # 添加weeks列，默认值为空字符串
            cursor.execute("ALTER TABLE schedules ADD COLUMN weeks VARCHAR(100) DEFAULT ''")
            conn.commit()
            print("已成功为schedules表添加weeks列")
        else:
            print("schedules表已经有weeks列")
            
    except Exception as e:
        print(f"添加列过程中发生错误: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_weeks_column()