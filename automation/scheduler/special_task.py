### scheduler/special_task.py
import threading
import time
import config.config
from utils.log import logger
import uuid


def start_click_say_btn_timer(vm_index: int, interval: int = 150):
    """
    开启 CLICK-SAY-BTN 定时点击任务，直到出现 EXPORT-ALL-DATA 为止
    """
    def run():
        logger.info(f"[特殊任务] VM{vm_index+1} 启动定时点击线程")
        config.config.SPECIAL_TASK_ACTIVE[vm_index] = True
        while config.config.SPECIAL_TASK_ACTIVE[vm_index]:
            time.sleep(interval)
            if config.config.interrupt_queues[vm_index].empty():
                config.config.interrupt_queues[vm_index].put({
                    "id": str(uuid.uuid4()),
                    "type": "prevent_afk_click",
                    "target_quadrant": vm_index,
                    "step_index": 0,
                    "extra": {},
                    "status": "pending"
                })
                logger.info(f"[特殊任务] VM{vm_index + 1} 推送 prevent_afk_click 打断任务")
            else:
                logger.info(f"[特殊任务] VM{vm_index + 1} 打断队列未空，跳过本轮推送")
        with config.config.interrupt_queues[vm_index].mutex:
            config.config.interrupt_queues[vm_index].queue.clear()
        logger.info(f"[特殊任务] VM{vm_index + 1} 定时点击线程已关闭，任务队列清空")

    threading.Thread(target=run, daemon=True).start()


def start_relink_battle_timer(vm_index: int, step_index: int, interval: int = 150):
    """
    开启定时启动battle任务，直到出现 具体标志 为止
    """
    def run():
        logger.info(f"[特殊任务] VM{vm_index + 1} 启动定时点击线程")
        config.config.SPECIAL_TASK_RELINK_BATTLE[vm_index] = True
        while config.config.SPECIAL_TASK_RELINK_BATTLE[vm_index]:
            time.sleep(interval)
            if config.config.interrupt_queues[vm_index].empty():
                config.config.interrupt_queues[vm_index].put({
                    "id": str(uuid.uuid4()),
                    "type": "battle_relink",
                    "target_quadrant": vm_index,
                    "step_index": step_index,
                    "extra": {},
                    "status": "pending"
                })
                logger.info(f"[特殊任务] VM{vm_index + 1} 推送 relink_battle 打断任务")
            else:
                logger.info(f"[特殊任务] VM{vm_index + 1} 打断队列未空，跳过本轮推送")
        with config.config.interrupt_queues[vm_index].mutex:
            config.config.interrupt_queues[vm_index].queue.clear()
        logger.info(f"[特殊任务] VM{vm_index + 1} 定时点击线程已关闭，任务队列清空")

    threading.Thread(target=run, daemon=True).start()
