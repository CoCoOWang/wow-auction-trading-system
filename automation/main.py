# magic_wow_automation/main.py

from utils.log import logger
import threading
import time
from task_executor.executor_main import execute_task
from task_executor.submit_manager import dispatch_initial_tasks, handle_task_failure
from task_executor.task_management import task_queues, submit_script_task
from task_executor.task_chain import get_loop_next_task
from utils.system_checker import is_process_running, close_process, is_login_screen
from utils.task_progress import get_last_completed_task
from vm_control import linear_boot_vms
from task_executor.mouse_keyboard_action import click_tab_by_index
from config.config import interrupt_queues, NUM_VMS_TO_START, SPECIAL_TASK_ACTIVE, retry_counters, MAX_RETRY,\
    RETRY_INTERVAL, CAPTURE_MODE, RESET_ALL_TASKS, SPECIAL_TASK_RELINK_BATTLE
from utils.offset_cache import load_offsets_into_memory
from utils.task_state import set_current_day, set_relogin_wow_state


# 动态生成 current_tasks 字典
current_tasks = {q: None for q in range(NUM_VMS_TO_START)}


def serial_execution_loop_with_retry():
    """
    串行轮询执行任务，每个象限单独计数失败次数，失败可重试，超过最大次数记录到数据库
    """
    while True:

        # 优先处理中断任务
        for vm_index in range(NUM_VMS_TO_START):
            if not interrupt_queues[vm_index].empty():
                interrupt_task = interrupt_queues[vm_index].get()
                logger.warning(f"[打断任务] 执行 VM{vm_index + 1} 的特殊点击任务：{interrupt_task['type']}")

                click_tab_by_index(vm_index)
                time.sleep(1)
                execute_task(interrupt_task, vm_index)
                # 继续下一轮
                break

        for i in range(NUM_VMS_TO_START):
            if SPECIAL_TASK_ACTIVE[i] or SPECIAL_TASK_RELINK_BATTLE[i]:
                logger.info(f"[跳过] VM{i+1} 处于特殊任务状态，跳过主任务调度")
                continue

            if not task_queues[i].empty():
                task = task_queues[i].get()
                # # 判断是否跳过
                # if skip_condition(task):
                #     logger.info(f"[任务跳过] 今日已完成任务 {task['type']}，跳过")
                #     continue
                logger.info(f"[任务调度] 切换至 VM{i + 1} 执行任务")
                click_tab_by_index(i)
                time.sleep(1)
                result = execute_task(task, i)
                if result:
                    retry_counters[i] = 0
                    current_tasks[i] = task['type']
                else:
                    retry_counters[i] += 1
                    if retry_counters[i] <= MAX_RETRY:
                        logger.warning(f"[调度器] 象限{i} 重试第 {retry_counters[i]} 次任务：{task['type']}")
                        # 重新提交 task，带上当前 step_index
                        submit_script_task(task["type"], quadrant=i, extra_data=task.get("extra"), task_id=task.get("id"), step_index=task.get("step_index"))
                    else:
                        handle_task_failure(i, task["type"])
            else:
                # 判断任务链中是否还有任务，有的话加上
                logger.info(f"获取下一个任务")
                next_task, step_index = get_loop_next_task(current_tasks[i], i)
                if next_task:
                    if next_task == 'battle_relink':
                        logger.info("进行重复登录战网任务")
                    else:
                        logger.info(f"[任务链] 当前任务 {current_tasks[i]} → 下一任务 {next_task}")
                        submit_script_task(next_task, quadrant=i, step_index=step_index)
                else:
                    logger.info(f"[任务链] 当前任务 {current_tasks[i]} 没有后续任务，等待外部指令")

        time.sleep(RETRY_INTERVAL)


def handle_recovery_for_quadrant(quadrant):
    logger.info(f"[恢复判断] 开始处理象限{quadrant}")

    if not is_process_running("Wow.exe"):
        logger.warning(f"[回退] 魔兽世界未运行，提交任务 enter_game")
        submit_script_task("enter_game", quadrant=quadrant)
        return

    # ✅ 假设未来可以通过图像识别判断是否停留在登录界面
    if is_login_screen():  # 可自定义（暂时略）
        logger.warning(f"[重启游戏] 当前停留在登录界面，自动关闭游戏并回退")
        close_process("Wow.exe")
        submit_script_task("enter_game", quadrant=quadrant)
        return

    # ✅ 如果已在游戏中
    last_task = get_last_completed_task(quadrant)
    logger.info(f"[进度查询] 象限{quadrant}已完成任务: {last_task}")

    next_task = get_loop_next_task(last_task, quadrant)
    if next_task:
        logger.info(f"[恢复] 提交任务 {next_task}")
        submit_script_task(next_task, quadrant=quadrant)
    else:
        logger.info(f"[已完成] 象限{quadrant}所有任务已完成")


def start_automation():
    if CAPTURE_MODE:
        logger.info("系统截图中...")
        from utils.screen_tools import capture_multiple_screenshots
        capture_multiple_screenshots(interval=2, count=20)
    else:
        logger.info("系统初始化中...")

        load_offsets_into_memory()  # 或者分VM传 vm_tag/screen

        # 设置当前日期，YYYY-MM-DD 格式
        set_current_day()

        # 查询设置是否是半途打开EXCEL
        set_relogin_wow_state()

        # 启动虚拟机
        linear_boot_vms()

        logger.info("系统启动完成，进入主循环")

        if RESET_ALL_TASKS:
            logger.warning("[重启模式] RESET_ALL_TASKS = True → 所有任务将从头开始执行")
            dispatch_initial_tasks()
        else:
            logger.info("[恢复模式] 根据运行状态恢复任务")
            for q in range(NUM_VMS_TO_START):  # 动态处理虚拟机数量
                handle_recovery_for_quadrant(q)

        t = threading.Thread(target=serial_execution_loop_with_retry)
        t.daemon = True
        t.start()
        logger.info("串口任务执行器启动完成")

        while True:
            time.sleep(1)


if __name__ == "__main__":
    start_automation()

