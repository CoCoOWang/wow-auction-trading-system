import openpyxl
from .logger import logger

# 定义全局变量
known_sheets = set()


def reset_known_sheets():
    """ 清空已知的 Sheet 页（当发现新文件时调用） """
    global known_sheets
    known_sheets.clear()
    logger.info("🔄 已清空 known_sheets，全局变量重置")


def get_existing_sheets(file_path):
    """ 获取当前 Excel 文件的所有 Sheet 页 """
    try:
        workbook = openpyxl.load_workbook(file_path)
        return set(workbook.sheetnames)
    except Exception as e:
        logger.error(f"❌ 无法读取 Excel: {e}")
        return set()


def watch_sheets(file_path, sheet_queue):
    """ 检测新增的 Sheet 页，使用全局变量 known_sheets """
    global known_sheets

    try:
        current_sheets = get_existing_sheets(file_path)
        new_sheets = current_sheets - known_sheets  # 找到新 Sheet 页

        for sheet_name in sorted(new_sheets):
            sheet_name_right_part = sheet_name.split(" ")[1]
            if sheet_name_right_part == "end":
                formatted_time = sheet_name
                has_stopped = True
            else:
                formatted_time = f"{sheet_name.replace('_', ':')}"
                has_stopped = False
            logger.info(f"🆕 发现新 Sheet: {sheet_name}, 解析时间: {formatted_time}")
            sheet_queue.put((file_path, formatted_time, has_stopped, sheet_name))

        # 更新全局变量
        known_sheets.update(sorted(new_sheets))
    except Exception as e:
        logger.error(f"❌ 监听 Sheet 页异常: {e}")
