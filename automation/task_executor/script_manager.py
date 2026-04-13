# magic_wow_automation/task_executor/script_manager.py

from utils.db import get_db_connection
from utils.log import logger
import os, json

SCRIPT_DIR = os.path.join(os.path.dirname(__file__), "../scripts")


def get_task_script(task_type):
    """
    优先从数据库加载任务脚本，如果失败则回退本地 JSON
    """
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM task_script WHERE task_type = %s", (task_type,))
            script = cursor.fetchone()
            if not script:
                raise Exception("数据库中未找到任务脚本")

            script_id = script["id"]
            cursor.execute("""
                SELECT step_order, action_type, target_image, click_x, click_y, input_text, delay_time
                FROM task_step
                WHERE script_id = %s
                ORDER BY step_order ASC
            """, (script_id,))
            steps = cursor.fetchall()

            formatted_steps = []
            for step in steps:
                step_obj = {
                    "description": f"步骤{step['step_order']}: {step['action_type']}",
                    "action": step['action_type'],
                    "target_image": step['target_image'],
                    "click_x": step['click_x'],
                    "click_y": step['click_y'],
                    "input_text": step['input_text'],
                    "delay": step['delay_time']
                }
                formatted_steps.append({k: v for k, v in step_obj.items() if v is not None})

            logger.info(f"[MySQL] 成功加载任务脚本: {task_type}")
            return {"steps": formatted_steps}

    except Exception as e:
        logger.warning(f"[MySQL] 加载任务 {task_type} 失败，尝试本地加载: {e}")
    finally:
        try:
            connection.close()
        except:
            pass

    # 回退到本地 JSON
    json_path = os.path.join(SCRIPT_DIR, f"{task_type}.json")
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    logger.error(f"[Script] 未找到任务脚本：{task_type}")
    return None
