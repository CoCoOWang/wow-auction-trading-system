# 窗口管理（移动、激活）
# magic_wow_automation/window_management.py
from utils.log import logger
import pygetwindow as gw
import win32gui
import pyautogui
import time
import win32con


def move_window(title, x, y, width, height):
    """
    将指定标题的窗口移动到指定位置并调整大小
    """
    win_list = gw.getWindowsWithTitle(title)
    if win_list:
        window = win_list[0]
        logger.info(f"移动窗口 {title} 到位置 ({x},{y}) 大小 ({width}x{height})")
        window.moveTo(x, y)
        window.resizeTo(width, height)
    else:
        logger.error(f"未找到窗口：{title}")


def bring_to_front(title):
    """
    将指定标题的窗口置顶
    """
    win_list = gw.getWindowsWithTitle(title)
    if win_list:
        window = win_list[0]
        logger.info(f"激活窗口 {title}")
        window.activate()
    else:
        logger.error(f"未找到窗口：{title}")


def get_window_rect(window_title):
    """
    获取指定窗口标题的窗口矩形坐标 (left, top, right, bottom)
    如果窗口未找到则返回 None
    """
    hwnd = win32gui.FindWindow(None, window_title)
    if hwnd == 0:
        return None

    rect = win32gui.GetWindowRect(hwnd)
    left, top, right, bottom = rect
    return {
        "left": left,
        "top": top,
        "right": right,
        "bottom": bottom,
        "width": right - left,
        "height": bottom - top
    }


def minimize_window(title_keyword):
    """
    根据窗口标题关键字将窗口最小化
    :param title_keyword: 窗口标题的一部分
    """
    hwnd = win32gui.FindWindow(None, None)
    hwnd = find_window_by_title(title_keyword)
    if hwnd:
        win32gui.ShowWindow(hwnd, win32con.SW_HIDE)

        # win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        # win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)

        # win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        logger.info(f"[窗口管理] 最小化窗口：{title_keyword}")
    else:
        logger.warning(f"[窗口管理] 未找到窗口：{title_keyword}")


def restore_window(title_keyword):
    """
    将指定标题的窗口从最小化状态恢复显示并激活
    :param title_keyword: 窗口标题的一部分
    """
    hwnd = find_window_by_title(title_keyword)
    if hwnd:
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        # win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)  # 恢复最小化状态
        win32gui.SetForegroundWindow(hwnd)             # 置于前台
        logger.info(f"[窗口管理] 恢复显示窗口：{title_keyword}")
    else:
        logger.warning(f"[窗口管理] 未找到窗口：{title_keyword}")


def find_window_by_title(title_keyword):
    """
    根据窗口标题关键字查找窗口句柄
    """
    def callback(hwnd, result):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title_keyword.lower() in title.lower():
                result.append(hwnd)
    matches = []
    win32gui.EnumWindows(callback, matches)
    return matches[0] if matches else None
