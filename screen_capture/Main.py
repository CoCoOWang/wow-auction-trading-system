#导入需要的库
import win32gui, win32ui, win32con
import cv2
import numpy
import time
import datetime
import os

from res.utils.WindowsApi import winapi


def getFileName(output_folder):

    # 获取当前时间
    current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # 创建输出文件夹（如果不存在）
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

        # 生成文件名
    file_name = f"{current_time}.jpg"
    output_path = os.path.join(output_folder, file_name)
    return output_path


hwnd = winapi.getTitleHwnd("Chrome Legacy Window")
wow_rect = winapi.getWinRect(hwnd)
print(wow_rect)
top = wow_rect['top']
bot = wow_rect['bot']
left = wow_rect['left']
right = wow_rect['right']


for i in range(99):

    im_opencv = winapi.getScreen()

    game_img = im_opencv[top:bot,left:right]

    filename = getFileName("res/img")

    cv2.imwrite(filename,game_img,[int(cv2.IMWRITE_JPEG_QUALITY), 100]) #保存

    time.sleep(2)
