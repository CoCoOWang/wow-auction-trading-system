# utils/task_progress.py

from utils.db import get_db_connection
from task_executor.task_chain import TASK_CHAIN

def get_last_completed_task(quadrant):
    """
    查询数据库中该象限上一次完成的任务链节点
    """
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            for task in reversed(TASK_CHAIN):
                cursor.execute("""
                    SELECT COUNT(*) AS cnt
                    FROM task_execution_log
                    WHERE task_type = %s AND quadrant = %s AND status = 'done' AND DATE(executed_at) = CURDATE()
                """, (task, quadrant))
                result = cursor.fetchone()
                if result['cnt'] > 0:
                    return task
    finally:
        conn.close()
    return None
