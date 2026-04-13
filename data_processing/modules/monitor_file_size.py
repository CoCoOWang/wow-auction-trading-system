import os
import time
import threading
from .watch_sheets import watch_sheets
from .logger import logger

WAIT_TIME_AFTER_CHANGE = 60

def monitor_file_size(file_path, sheet_queue):
    """ 监听文件大小，直到文件稳定，支持多个 Sheet 监听 """
    last_size = os.path.getsize(file_path)
    stable_time = 0
    t = threading.current_thread()

    while getattr(t, "do_run", True):
        try:
            time.sleep(5)
            current_size = os.path.getsize(file_path)

            if current_size == last_size:
                stable_time += 5
                if stable_time >= WAIT_TIME_AFTER_CHANGE:
                    logger.info(f"✅ 文件写入稳定: {file_path}")
                    watch_sheets(file_path, sheet_queue)  # **每次文件稳定后检测新 Sheet**
                    stable_time = 0  # **重置计数，允许多次监听**
            else:
                stable_time = 0
                last_size = current_size  # **更新文件大小**

        except PermissionError as e:  # **专门捕获文件占用错误**
            logger.warning(f"⚠️ 文件被占用，等待重试: {e}")
            time.sleep(2)  # **短暂等待，避免高频重试**
            continue  # **跳过当前循环迭代，直接重试**

        except Exception as e:
            logger.error(f"❌ 监听文件大小异常: {e}")
            time.sleep(2)  # **避免异常导致 CPU 占用过高**
            continue  # **直接重试**