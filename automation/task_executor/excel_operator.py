# 控制Excel窗口内容
# magic_wow_automation/task_executor/excel_operator.py
import pyautogui
import time
from utils.log import logger


def scroll_excel(amount=1):
    """
    滚动Excel表格
    :param amount: 滚动步数（正负表示方向）
    """
    logger.info(f"滚动Excel {amount} 步")
    pyautogui.scroll(-amount * 100)  # 每步100像素
    time.sleep(0.2)


def paste_to_excel():
    """
    粘贴剪贴板内容到当前Excel单元格
    """
    logger.info("在Excel中粘贴内容")
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.5)


def select_all_in_excel():
    """
    全选Excel当前表格内容
    """
    logger.info("全选Excel表格")
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.3)

