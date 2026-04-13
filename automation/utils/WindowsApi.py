# utils/WindowsApi.py
import win32gui, win32ui, win32con
import numpy as np
import cv2


class WindowsApi:
    def __init__(self):
        pass


    def getTitleHwnd(self, win_title):
        """模糊匹配窗口标题，返回第一个符合的句柄"""
        hd = win32gui.GetDesktopWindow()
        hwndChildList = []
        win32gui.EnumChildWindows(hd, lambda hwnd, param: param.append(hwnd), hwndChildList)

        for hwnd in hwndChildList:
            title = win32gui.GetWindowText(hwnd)
            if win_title in title:
                return hwnd
        return None


    def getWinRect(self, hwnd):
        """获取指定窗口的矩形坐标和尺寸"""
        rect = win32gui.GetWindowRect(hwnd)
        left, top, right, bot = rect
        return {
            "left": left, "top": top, "right": right, "bot": bot,
            "width": right - left, "height": bot - top
        }


    def getScreen(self):
        """截取全屏图像（返回OpenCV格式）"""
        return self._capture_region(*win32gui.GetWindowRect(win32gui.GetDesktopWindow()))


    def getWindowScreenshot(self, hwnd):
        """截取指定窗口的图像（返回OpenCV格式）"""
        rect = win32gui.GetWindowRect(hwnd)
        return self._capture_region(*rect)


    def _capture_region(self, left, top, right, bot):
        width, height = right - left, bot - top

        hWndDC = win32gui.GetWindowDC(0)
        mfcDC = win32ui.CreateDCFromHandle(hWndDC)
        saveDC = mfcDC.CreateCompatibleDC()
        saveBitMap = win32ui.CreateBitmap()
        saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
        saveDC.SelectObject(saveBitMap)
        saveDC.BitBlt((0, 0), (width, height), mfcDC, (left, top), win32con.SRCCOPY)

        img = np.frombuffer(saveBitMap.GetBitmapBits(True), dtype='uint8').reshape((height, width, 4))
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        win32gui.DeleteObject(saveBitMap.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        win32gui.ReleaseDC(0, hWndDC)

        return img


# 单例实例
winapi = WindowsApi()
