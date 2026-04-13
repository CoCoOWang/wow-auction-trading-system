# modules/file_watcher.py
import os
import time
from queue import Queue
from .logger import logger

project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCH_FOLDER = os.path.join(project_dir, "data")

file_list = []  # 仅用于本进程去重


def watch_new_files(file_queue: Queue, poll_secs: int = 5):
    """ 启动即全量扫描（排序），之后每 poll_secs 发现新文件就入队 """
    logger.info(f"监控目录: {WATCH_FOLDER}")

    # 首次全量扫描（排序）
    try:
        all_files = [f for f in os.listdir(WATCH_FOLDER) if f.lower().endswith((".xlsx", ".xlsm")) and not f.startswith("~$")]
        for file_name in sorted(all_files):  # 排序保证重启后从头解析
            file_path = os.path.join(WATCH_FOLDER, file_name)
            if file_name not in file_list:
                file_queue.put(file_path)
                file_list.append(file_name)
                logger.info(f"初始入队: {file_path}")
    except FileNotFoundError:
        os.makedirs(WATCH_FOLDER, exist_ok=True)

    # 持续发现增量文件
    while True:
        try:
            current_files = [f for f in os.listdir(WATCH_FOLDER) if f.lower().endswith((".xlsx", ".xlsm")) and not f.startswith("~$")]
            for file_name in sorted(current_files):
                if file_name not in file_list:
                    file_path = os.path.join(WATCH_FOLDER, file_name)
                    file_queue.put(file_path)
                    file_list.append(file_name)
                    logger.info(f"发现新文件: {file_path}")
            time.sleep(poll_secs)
        except Exception as e:
            logger.error(f"监听新文件异常: {e}")
            time.sleep(2)
