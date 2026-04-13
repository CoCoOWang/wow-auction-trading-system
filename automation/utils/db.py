import pymysql

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "123456",
    "database": "wow_auction",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor  # 新增这一行，关键！
}


def get_db_connection():
    """ 获取 MySQL 数据库连接 """
    return pymysql.connect(**DB_CONFIG)


def log_task_execution(task_id, task_type, quadrant, status, message="", step_index=0):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """
            INSERT INTO task_execution_log (task_id, task_type, quadrant, status, message, step_index)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (task_id, task_type, quadrant, status, message, step_index))
            conn.commit()
    except Exception as e:
        print(f"[DB] 任务日志写入失败: {e}")
    finally:
        try:
            conn.close()
        except:
            pass
