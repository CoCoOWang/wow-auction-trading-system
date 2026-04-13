# task_executor/task_chain.py
import config.config
from utils.log import logger
from task_executor.task_management import submit_script_task
from scheduler.special_task import start_relink_battle_timer
from datetime import datetime
from utils.task_state import update_updating_sheet_content, get_updating_sheet_content

TASK_CHAIN = [
    "prepare_env",
    "enter_game",           # 点击“开始游戏” → 启动魔兽世界
    "scan_auction",         # 进入游戏后的任务集合
    "export_auction_data",  # 导出拍卖行数据
    "paste_auction_data",   # 粘贴拍卖行数据
    "relogin_wow"           # 重新登录WOW
]


def get_loop_next_task(current_task, vm_index):
    """
    支持 export_auction_data 与 paste_auction_data 的循环控制逻辑
    """
    if config.config.WOW_OFFLINE_STATUS[vm_index]:
        config.config.WOW_OFFLINE_STATUS[vm_index] = False
        return "quit_wow", 0

    if current_task == "quit_wow":
        logger.info("登录battle失败，开始重复登录battle定时计划")
        start_relink_battle_timer(vm_index, 0)
        return None, 0

    if current_task == "reopen_wow_then_close_window":
        logger.info("本次复制失败，开始重新扫描")
        return "relogin_wow", 0  # 跳转到 relogin

    if current_task == "paste_auction_data":
        if not config.config.HAS_EXPORT_ALL_DATA[vm_index]:
            return "export_auction_data", 1  # 回到导出任务继续执行
        else:
            update_updating_sheet_content(vm_id=vm_index, task_name='update_sheet_content', is_updating_sheet_content=0, task_date=config.config.CURRENT_DAY)
            return "relogin_wow", 0  # 跳转到 relogin

    elif current_task == "relogin_wow":
        return "scan_auction", 0  # 循环回归下一轮

    elif current_task == "export_auction_data":
        # YYYY-MM-DD 格式
        today_str = datetime.now().strftime("%Y-%m-%d")
        if config.config.CURRENT_DAY == today_str:
            return get_next_task(current_task), 0
        else:
            is_updating_sheet_content = get_updating_sheet_content(vm_id=int(vm_index), task_name='update_sheet_content', task_date=config.config.CURRENT_DAY)
            if is_updating_sheet_content:
                return get_next_task(current_task), 0
            return "recreate_wps", 0

    elif current_task == "recreate_wps":
        config.config.IS_RELOGIN_WOW_FLG[vm_index] = False
        config.config.IS_FIRST_COPY_OPERATE[vm_index] = True
        return "paste_auction_data", 2

    else:
        # 默认顺序跳转
        return get_next_task(current_task), 0


def relink_battle_task(current_task, i):
    if current_task == "battle_relink":
        step_index = config.config.LINK_ENTER_GAME_INDEX
        if step_index:
            next_task = "enter_game"
            logger.info(f"[任务链] 当前任务 {current_task} → 下一任务 {next_task}")
            submit_script_task(next_task, quadrant=i, step_index=step_index)


def quit_and_login_wow_task(i):
    submit_script_task("reopen_wow_then_close_window", quadrant=i, step_index=0)


def get_previous_task(task_type):
    """
    回退到 task_type 之前的任务（如 enter_game → start_battlenet）
    """
    try:
        idx = TASK_CHAIN.index(task_type)
        return TASK_CHAIN[idx - 1] if idx > 0 else task_type
    except ValueError:
        return task_type


def get_next_task(task_type="prepare_env"):
    """
    获取 task_type 之后的任务
    """
    try:
        idx = TASK_CHAIN.index(task_type)
        return TASK_CHAIN[idx + 1] if idx < len(TASK_CHAIN) - 1 else None
    except ValueError:
        return None
