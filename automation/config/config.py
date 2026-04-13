from utils.config_loader import config

NUM_VMS_TO_START = config.get("num_vms_to_start", 2)

# 全局重试设置
MAX_RETRY = 5
RETRY_INTERVAL = 3  # 秒
retry_counters = [0, 0, 0, 0]
RESET_ALL_TASKS = True  # True 表示从头开始；False 表示恢复失败任务并跳过已执行的
CAPTURE_MODE = False # True 表示截图模式；False 表示任务模式
# 是否处于特殊任务状态（如 VM 正在 scan_auction 查询中）
SPECIAL_TASK_ACTIVE = [False] * NUM_VMS_TO_START  # 根据虚拟机数量调整

# 是否处于特殊任务状态（如 VM 正在 relink_battle）
SPECIAL_TASK_RELINK_BATTLE = [False] * NUM_VMS_TO_START  # 根据虚拟机数量调整

# 打断任务队列
from queue import Queue
interrupt_queues = [Queue() for _ in range(NUM_VMS_TO_START)]

# 是否是第一个sheet
IS_FIRST_COPY_OPERATE = [True] * NUM_VMS_TO_START

# 是否导出所有数据
HAS_EXPORT_ALL_DATA = [False] * NUM_VMS_TO_START

# 是否是重新登录状态
IS_RELOGIN_WOW_FLG = [False] * NUM_VMS_TO_START

# 魔兽世界掉线状态
WOW_OFFLINE_STATUS = [False] * NUM_VMS_TO_START  # 根据虚拟机数量调整

# 连接enter_game的序号
LINK_ENTER_GAME_INDEX = 0

# 记录当天日期
CURRENT_DAY = 0

# 数据库中的记录的当天日期
db_current_day_obj = [None] * NUM_VMS_TO_START

# 判断是否走了SHOPPING-BTN保底
shopping_btn_related_obj = [False] * NUM_VMS_TO_START

# 判断是否走了SEARCH-BTN保底
search_btn_related_obj = [False] * NUM_VMS_TO_START

# 判断是否展开了EXCEL文件页
is_show_excel_obj = [False] * NUM_VMS_TO_START

# 判断是否是第一个CELL格
is_first_cell_obj = [True] * NUM_VMS_TO_START

# 记录当前虚拟机的sheet_name的位置
CURRENT_VM_SHEETNAME_LOCATION = [(0, 0)] * NUM_VMS_TO_START

# 记录insert_work_sheet相对于sheet_name的偏移量
INSERT_WORK_SHEET_OFFSET = (87, -513)

# 记录当前的恢复虚拟机页面的点击位置
VM_RECOVER_CLICK_POS = [(576, 1080), (None, None), (None, None), (None, None)]
