# 获取窗口句柄、屏幕截图
# magic_wow_automation/utils/log.py
import logging
import os

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",  # 指定时间格式
    handlers=[
        logging.FileHandler(f"{LOG_DIR}/system_debug.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# 外部直接使用 logger 对象
logger = logging.getLogger("wow_automation")
