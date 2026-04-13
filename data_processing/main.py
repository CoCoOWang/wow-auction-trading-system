import queue
import threading
import time
from modules.file_watcher import watch_new_files
from modules.monitor_file_size import monitor_file_size
from modules.watch_sheets import reset_known_sheets
from modules.logger import logger
import modules.data_parser

file_queue = queue.Queue()
sheet_queue = queue.Queue()
current_file = None
monitor_thread = None
lock = threading.Lock()


def handle_new_files():
    """ 监听新文件并处理文件大小变化 """
    global current_file, monitor_thread
    while True:
        try:
            if modules.data_parser.file_parsing_status:
                new_file = file_queue.get()
                if not new_file:
                    logger.warning("发现空文件，跳过...")
                    time.sleep(10)  # **减少 CPU 占用**
                    continue

                reset_known_sheets()  # **清空已知 Sheet 页**

                modules.data_parser.file_parsing_status = False

                # 切换到新文件，重置已知 Sheet，开启/切换监控线程
                with lock:
                    logger.info(f"发现新文件: {new_file}")

                    if monitor_thread and monitor_thread.is_alive():
                        logger.info(f"停止监听旧文件: {current_file}")
                        monitor_thread.do_run = False
                        monitor_thread.join()

                    current_file = new_file
                    logger.info(f"开始监听文件大小: {current_file}")

                    monitor_thread = threading.Thread(target=monitor_file_size, args=(current_file, sheet_queue), daemon=True)
                    monitor_thread.start()

            time.sleep(10)  # **减少 CPU 占用**

        except Exception as e:
            logger.error(f"❌ 处理新文件异常: {e}")
            time.sleep(10)  # **减少 CPU 占用**
            continue


def handle_sheets():
    """ 监听 Sheet 队列，解析 Sheet 页 """
    while True:
        try:
            if modules.data_parser.sheet_parsing_status:
                file_path, formatted_time, has_stopped, sheet_name = sheet_queue.get()
                if file_path and sheet_name:
                    logger.info(f"解析 Sheet 页: {sheet_name} in {file_path}")
                    modules.data_parser.parse_sheet_data(file_path, formatted_time, has_stopped, sheet_name)
            time.sleep(10)  # 避免 CPU 100% 占用
        except Exception as e:
            logger.error(f"❌ 处理 Sheet 页异常: {e}")
            time.sleep(10)  # **减少 CPU 占用**
            continue


def start_data_processing():
    threading.Thread(target=watch_new_files, args=(file_queue,), daemon=True).start()
    threading.Thread(target=handle_new_files, daemon=True).start()
    threading.Thread(target=handle_sheets, daemon=True).start()

    logger.info("data_processing 服务已启动")

    while True:
        time.sleep(1)


if __name__ == "__main__":
    start_data_processing()
