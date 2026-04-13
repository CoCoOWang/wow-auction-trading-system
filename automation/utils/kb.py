# kb.py
import time, ctypes, win32con, win32api, win32gui

# ---- Windows SendInput structures ----
PUL = ctypes.POINTER(ctypes.c_ulong)


class KEYBDINPUT(ctypes.Structure):
    _fields_ = (("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL))


class INPUT(ctypes.Structure):
    _fields_ = (("type", ctypes.c_ulong),
                ("ki", KEYBDINPUT))


SendInput = ctypes.windll.user32.SendInput


def _send_key(vk: int, down: bool):
    flags = 0 if down else win32con.KEYEVENTF_KEYUP
    ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=None)
    inp = INPUT(type=1, ki=ki)
    SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def _tap(vk: int, down_ms: float = 30):
    _send_key(vk, True)
    time.sleep(down_ms / 1000.0)
    _send_key(vk, False)


def release_modifiers():
    """保险：释放所有修饰键，避免残留导致组合键串键。"""
    for vk in (win32con.VK_CONTROL, win32con.VK_LCONTROL, win32con.VK_RCONTROL,
               win32con.VK_MENU, win32con.VK_LMENU, win32con.VK_RMENU,
               win32con.VK_SHIFT, win32con.VK_LSHIFT, win32con.VK_RSHIFT,
               win32con.VK_LWIN, win32con.VK_RWIN):
        _send_key(vk, False)
    time.sleep(0.02)


def warmup():
    """预热：敲一下 SHIFT，帮虚拟机抓取输入，配合增强型键盘稳定首发。"""
    _tap(win32con.VK_SHIFT, 50)
    time.sleep(0.03)


def send_combo(vks: list[int], inter_down_ms: int = 40, inter_up_ms: int = 30):
    """
    稳定发送组合键。按下顺序：v1↓, v2↓ ... 再逆序抬起：vn↑ ... v1↑
    """
    # 保守：发前先清修饰键
    release_modifiers()
    time.sleep(0.01)

    # 逐个按下
    for vk in vks:
        _send_key(vk, True)
        time.sleep(inter_down_ms / 1000.0)

    # 逆序抬起
    for vk in reversed(vks):
        _send_key(vk, False)
        time.sleep(inter_up_ms / 1000.0)

    # 收尾再清一次修饰键
    release_modifiers()


# ==== 常用封装 ====
def ctrl_key(vk: int):
    send_combo([win32con.VK_CONTROL, vk])


def ctrl_a(): ctrl_key(ord('A'))
def ctrl_c(): ctrl_key(ord('C'))
def ctrl_v(): ctrl_key(ord('V'))
def ctrl_s(): ctrl_key(ord('S'))
def ctrl_z(): ctrl_key(ord('Z'))
def ctrl_down(): ctrl_key(win32con.VK_DOWN)
def ctrl_up(): ctrl_key(win32con.VK_UP)


def tap_down(): _tap(win32con.VK_DOWN)
def tap_enter(): _tap(win32con.VK_RETURN)
def tap_esc(): _tap(win32con.VK_ESCAPE)
