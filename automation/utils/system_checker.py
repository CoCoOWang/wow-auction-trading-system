# utils/system_checker.py

import psutil
from task_executor.image_detection import model
from utils.WindowsApi import winapi


def is_process_running(name="Wow.exe"):
    """
    检查魔兽世界进程是否存在
    """
    for p in psutil.process_iter(['name']):
        if name.lower() in p.info['name'].lower():
            return True
    return False


def close_process(name="Wow.exe"):
    """
    关闭魔兽世界进程
    """
    for p in psutil.process_iter(['pid', 'name']):
        if name.lower() in p.info['name'].lower():
            p.terminate()
            return True
    return False


# 未来使用 YOLO 检测登录界面，也可以添加一个 is_login_screen() 函数。
def is_login_screen(conf=0.5):
    """
    使用YOLO模型判断是否处于登录界面
    """
    screenshot = winapi.getScreen()  # 实时桌面截图
    results = model(screenshot)

    for r in results:
        for i, cls_id in enumerate(r.boxes.cls):
            class_name = r.names[int(cls_id)]
            if class_name == "login_screen_indicator" and r.boxes.conf[i] > conf:
                return True
    return False
