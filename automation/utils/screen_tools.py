import os
import datetime
import cv2
import time
from utils.WindowsApi import winapi
from utils.log import logger


def capture_multiple_screenshots(interval=2, count=20, folder="res/img", prefix="snapshot"):
    os.makedirs(folder, exist_ok=True)
    logger.info(f"[截图模式] 开始每 {interval}s 截图一次，保存 {count} 张到 {folder}")

    for i in range(count):
        img = winapi.getScreen()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = os.path.join(folder, f"{prefix}_{i + 1}_{timestamp}.jpg")
        cv2.imwrite(path, img, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        logger.info(f"[截图保存] 第 {i + 1} 张保存至：{path}")
        time.sleep(interval)

    logger.info("[截图模式] 已完成所有截图任务")
