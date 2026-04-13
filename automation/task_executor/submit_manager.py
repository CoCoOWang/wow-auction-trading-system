from utils.log import logger
from task_executor.task_management import submit_script_task
import config.config
from utils.task_state import select_db_current_day

# 全局配置
MAX_RETRY = 5
RETRY_INTERVAL = 10  # 秒

# 每象限当前重试计数器
retry_counters = [0, 0, 0, 0]


def dispatch_initial_tasks(task_type="prepare_env"):
    for q in range(config.config.NUM_VMS_TO_START):
        # 查询数据库日期
        if task_type=="prepare_env":
            config.config.db_current_day_obj[q] = select_db_current_day(q, 'save_file', config.config.CURRENT_DAY)
        submit_script_task(task_type, quadrant=q)


def handle_task_failure(quadrant, task_type):
    # from utils.db import log_task_execution

    logger.error(f"[调度器] 象限{quadrant}任务重试超限，记入数据库")
    # log_task_execution("none", task_type, quadrant, "failed", "超出最大重试次数")

