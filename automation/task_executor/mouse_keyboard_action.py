# 鼠标键盘模拟操作
# magic_wow_automation/task_executor/mouse_keyboard_action.py
import pyautogui
from utils.log import logger
import time
import win32api
import win32con
import psutil
import win32gui
import win32process
import win32clipboard as cb
from utils.kb import warmup, release_modifiers, ctrl_a, ctrl_c, ctrl_v, ctrl_s, ctrl_z, ctrl_down, ctrl_up, tap_esc, tap_enter, tap_down

from task_executor.serial_operator import (
    USE_HARDWARE_MOUSE,
    get_serial_controller
)


# ── 常用 VK
VK = win32con
VK_CTRL_L, VK_CTRL_R = VK.VK_LCONTROL, VK.VK_RCONTROL
VK_SHIFT_L, VK_SHIFT_R = VK.VK_LSHIFT, VK.VK_RSHIFT
VK_MENU_L,  VK_MENU_R  = VK.VK_LMENU,  VK.VK_RMENU   # Alt
VK_DOWN, VK_UP = VK.VK_DOWN, VK.VK_UP


def encode_to_ch9329_keys(text: str) -> str:
    """
    将可视字符转为 CH9329 所需的键码字符串，每两个字符一组发送。
    比如输入：'2025-07-28'
    输出：'220022552D00772D2288'
    """
    mapping = {
        '0': '00', '1': '11', '2': '22', '3': '33', '4': '44',
        '5': '55', '6': '66', '7': '77', '8': '88', '9': '99', 'e': 'EE', 'n': 'NN', 'd': 'DD',
        '-': '2D', '_': '2D',  # 注意：'_' 需要 shift，不建议直接发
    }

    result = ""
    for ch in text:
        if ch in mapping:
            result += mapping[ch]
        else:
            raise ValueError(f"不支持字符：{ch}，请添加到映射表")
    return result


def robust_copy_auction_data(controller, max_retries=2):
    for attempt in range(1, max_retries + 1):
        logger.info(f"第 {attempt} 次尝试复制拍卖行数据")

        logger.info("开始发送 Ctrl + C")
        controller.send_ctrl_key("CC")  # Ctrl+C
        logger.info("结束发送 Ctrl + C")

        time.sleep(0.5)


def paste_text(text: str):
    # 置剪贴板
    cb.OpenClipboard()
    cb.EmptyClipboard()
    cb.SetClipboardText(text)
    cb.CloseClipboard()
    time.sleep(0.05)


def _sc(vk):  # 扫描码
    return win32api.MapVirtualKey(vk, 0)


def _is_extended(vk: int) -> bool:
    # 方向键/Ins/Del/Home/End/PgUp/PgDn 等是扩展键，需要 EXTENDED 标志
    return vk in {
        VK.VK_INSERT, VK.VK_DELETE, VK.VK_HOME, VK.VK_END,
        VK.VK_PRIOR,  # PageUp
        VK.VK_NEXT,   # PageDown
        VK.VK_LEFT, VK.VK_RIGHT, VK.VK_UP, VK.VK_DOWN,
        VK.VK_NUMLOCK, VK.VK_CANCEL, VK.VK_SNAPSHOT, VK.VK_DIVIDE
    }


def key_up(vk: int):
    flags = VK.KEYEVENTF_KEYUP | (VK.KEYEVENTF_EXTENDEDKEY if _is_extended(vk) else 0)
    win32api.keybd_event(vk, _sc(vk), flags, 0)


# ── 1) 黏连修复（最小侵入：在序列末尾调用一次）
def release_possible_stuck_modifiers():
    """尽量“解黏连”：Ctrl/Shift/Alt 左右键都抬起两遍，间隔极短"""
    mods = (VK_CTRL_L, VK_CTRL_R, VK_SHIFT_L, VK_SHIFT_R, VK_MENU_L, VK_MENU_R)
    for _ in range(2):
        for vk in mods:
            key_up(vk)
        time.sleep(0.01)


def execute_action(x, y, action='click', click_times=1, click_interval=0.5, content=None):
    """
    移动鼠标到指定位置并点击（可配置点击次数和间隔）

    :param x: 目标X坐标
    :param y: 目标Y坐标
    :param action: 操作类型
    :param click_times: 点击次数，默认1次
    :param click_interval: 每次点击之间的间隔秒数
    :param content: 输入内容（如用于 input_pwd）
    :return: True / False
    """
    try:

        logger.info(f"执行鼠标操作: ({x},{y}), 类型={action}, 次数={click_times}")

        if USE_HARDWARE_MOUSE:

            controller = get_serial_controller()
            if x and y:
                controller.move_mouse_abs(x, y)
            time.sleep(0.3)

            if action == 'double_click':
                logger.info("开始硬件双击")
                controller.double_click_mouse()
                logger.info("结束硬件双击")

            elif action == 'escape' or action == 'send_escape_three_times':
                logger.info("开始硬件点击ESC")
                for i in range(click_times):
                    logger.info(f"第 {i + 1} 次 ESC")
                    controller.send_single_key("ESC")  # 自定义封装方法，已自动 release
                    time.sleep(click_interval)
                logger.info("结束硬件点击ESC")

            elif action == 'enter':
                logger.info("开始硬件点击Enter")
                for i in range(click_times):
                    logger.info(f"第 {i + 1} 次 Enter")
                    controller.send_single_key("ENTER")  # 自定义封装方法，已自动 release
                    time.sleep(click_interval)
                logger.info("结束硬件点击Enter")

            elif action == 'right_click':
                logger.info("开始硬件右键点击")
                for i in range(click_times):
                    controller.click_mouse(button='right')
                    if i < click_times - 1:
                        time.sleep(click_interval)
                logger.info("结束硬件右键点击")

            # ✅ 正确的逻辑应该是：
            # 如果想输入小写 a，发送 AA，不加 shift
            # 如果想输入大写 A，发送 AA，加 shift
            # 如果想输入数字 3，发送 33，不加 shift
            elif action == 'input_pwd':
                logger.info("开始硬件密码输入")
                controller.click_mouse()
                time.sleep(0.3)
                controller.press_keys(content)
                logger.info("结束硬件密码输入")

            elif action == 'write_current_day' or action == 'write_now_time' or action == 'write_end_status':
                logger.info("开始硬件日期或者时间输入")
                keycode = encode_to_ch9329_keys(content)
                controller.press_keys(keycode)
                logger.info("结束硬件日期或者时间输入")

            elif action == 'ctrl_down':
                logger.info("[WinAPI] Ctrl + Down 开始发送")
                # 1. 按下 Ctrl
                win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
                time.sleep(0.05)
                # 2. 按下 Down Arrow
                win32api.keybd_event(win32con.VK_DOWN, 0, 0, 0)
                time.sleep(0.05)
                # 3. 释放 Down Arrow
                win32api.keybd_event(win32con.VK_DOWN, 0, win32con.KEYEVENTF_KEYUP, 0)
                time.sleep(0.5)
                # 4. 释放 Ctrl
                win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
                logger.info("[WinAPI] Ctrl + Down 结束发送")
                time.sleep(0.5)
                release_possible_stuck_modifiers()  # ← 最小改动：做一次清理
                time.sleep(0.5)
                # 2. 按下 Down Arrow
                win32api.keybd_event(win32con.VK_DOWN, 0, 0, 0)
                time.sleep(0.05)
                # 3. 释放 Down Arrow
                win32api.keybd_event(win32con.VK_DOWN, 0, win32con.KEYEVENTF_KEYUP, 0)

            elif action == 'ctrl_c':
                logger.info("开始发送 Ctrl + C")
                controller.send_ctrl_key("CC")  # Ctrl+C
                logger.info("结束发送 Ctrl + C")

                time.sleep(0.5)

            elif action == 'ctrl_a':
                logger.info("开始发送 Ctrl + A")
                controller.send_ctrl_key("AA")  # Ctrl+A
                logger.info("结束发送 Ctrl + A")

                time.sleep(0.5)

            elif action == 'ctrl_z':
                logger.info("[WinAPI] Ctrl + Z 开始发送")
                # 1. 按下 Ctrl
                win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
                time.sleep(0.05)
                # 2. 按下 Z
                win32api.keybd_event(ord('Z'), 0, 0, 0)
                time.sleep(0.05)
                # 3. 释放 Z
                win32api.keybd_event(ord('Z'), 0, win32con.KEYEVENTF_KEYUP, 0)
                time.sleep(0.5)
                # 4. 释放 Ctrl
                win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
                logger.info("[WinAPI] Ctrl + Z 结束发送")
                time.sleep(0.5)

            elif action == 'ctrl_s':
                logger.info("[WinAPI] Ctrl + S 开始发送")
                # 1. 按下 Ctrl
                win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
                time.sleep(0.05)
                # 2. 按下 S
                win32api.keybd_event(ord('S'), 0, 0, 0)
                time.sleep(0.05)
                # 3. 释放 S
                win32api.keybd_event(ord('S'), 0, win32con.KEYEVENTF_KEYUP, 0)
                time.sleep(0.5)
                # 4. 释放 Ctrl
                win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
                logger.info("[WinAPI] Ctrl + S 结束发送")
                time.sleep(0.5)

            elif action == 'move':
                logger.info("已经移动鼠标")

            else:
                logger.info("开始硬件单击")
                for i in range(click_times):
                    controller.click_mouse()
                    if i < click_times - 1:
                        time.sleep(click_interval)
                logger.info("结束硬件单击")

        return True
    except Exception as e:
        logger.error(f"鼠标操作失败: {e}")
        return False


def type_text(text):
    """
    输入文本（可用于搜索框）
    """
    try:
        pyautogui.typewrite(text, interval=0.05)
        logger.info(f"输入文字：{text}")
    except Exception as e:
        logger.error(f"输入文字失败: {e}")


TAB_BAR_POSITION = (1050, 15)  # 起始位置（你需要调试具体坐标）
TAB_WIDTH = 78  # 每个标签页宽度


def click_tab_by_index(index):
    logger.info(f"点击TAB页")
    x = TAB_BAR_POSITION[0] + index * TAB_WIDTH
    y = TAB_BAR_POSITION[1]
    if USE_HARDWARE_MOUSE:
        logger.info("开始硬件单击")
        controller = get_serial_controller()
        controller.move_mouse_abs(x, y)
        time.sleep(0.3)
        controller.click_mouse()
        time.sleep(1)
        logger.info("结束硬件单击")
    else:
        logger.info("开始单击（pyautogui）")
        pyautogui.moveTo(x, y, duration=0.3)
        time.sleep(1)  # 稳定延迟
        pyautogui.click()
        time.sleep(1)
        logger.info("结束单击（pyautogui）")


def activate_vm_then_click(delay=0.5):
    """
    第一次点击虚拟机TAB激活焦点，再点击目标位置。

    :param delay: 激活与真实点击之间的间隔
    """
    x = 3
    y = 967
    if USE_HARDWARE_MOUSE:
        logger.info("开始硬件单击")
        controller = get_serial_controller()
        controller.move_mouse_abs(x, y)
        time.sleep(0.3)
        controller.click_mouse()
        time.sleep(delay)
        logger.info("结束硬件单击")
    else:
        logger.info("开始单击（pyautogui）")
        pyautogui.moveTo(x, y, duration=0.3)  # 清空 hover
        time.sleep(0.5)
        pyautogui.click()
        time.sleep(delay)
        logger.info("结束单击（pyautogui）")
