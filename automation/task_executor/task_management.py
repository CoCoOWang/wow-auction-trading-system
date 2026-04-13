# magic_wow_automation/task_management.py
from utils.log import logger
import queue
import uuid
from utils.db import get_db_connection

# 每个象限独立任务队列（0~3）
task_queues = [queue.Queue() for _ in range(4)]

# 已恢复或已提交的任务类型 + 象限组合
submitted_task_keys = set()


def add_task(quadrant, task):
    """
    添加任务到指定象限的队列（调度器用）
    """
    task_queues[quadrant].put(task)
    logger.info(f"添加任务到象限{quadrant}：{task}")


def submit_script_task(task_type, quadrant=0, extra_data=None, task_id=None, step_index=0):
    # key = f"{task_type}-{quadrant}"
    # if key in submitted_task_keys:
    #     logger.info(f"[任务跳过] 已在本轮提交过 {key}，跳过")
    #     return None

    task = {
        "id": task_id or str(uuid.uuid4()),
        "type": task_type,
        "status": "pending",
        "target_quadrant": quadrant,
        "extra": extra_data or {},
        "step_index": step_index
    }

    from task_executor.task_management import add_task
    add_task(quadrant, task)

    # submitted_task_keys.add(key)  # 标记本轮已提交
    # logger.info(f"[任务提交] {key} → 已入队")
    return task


def skip_condition(task):
    """
    判断一个任务是否可以跳过（如今日已完成 + 非required）
    """
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) AS cnt
                FROM task_execution_log
                WHERE task_type = %s AND quadrant = %s AND status = 'done' AND DATE(executed_at) = CURDATE()
            """, (task['type'], task['target_quadrant']))
            result = cursor.fetchone()
            # 若今日已执行过，并且不是强制任务，则跳过
            if result["cnt"] > 0 and not task.get("required", False):
                return True
    finally:
        conn.close()
    return False
