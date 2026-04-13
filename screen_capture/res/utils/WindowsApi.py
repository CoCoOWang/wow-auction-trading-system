#导入需要的库
import win32gui, win32ui, win32con
import cv2
import numpy

class WindowsApi():

    def __init__(self):
        pass


    def getTitleHwnd(self,win_title):
        #  GetDesktopWindow 获得代表整个屏幕的一个窗口（桌面窗口）句柄
        hd = win32gui.GetDesktopWindow()
        # 初始化一个空列表，用于存储桌面窗口的所有子窗口句柄
        hwndChildList = []
        #   EnumChildWindows 为指定的父窗口枚举子窗口
        win32gui.EnumChildWindows(hd, lambda hwnd, param: param.append(hwnd), hwndChildList)

        for hwnd in hwndChildList:
            #   GetWindowText 取得一个窗体的标题（caption）文字，或者一个控件的内容
            # print("句柄：", hwnd, "标题：", win32gui.GetWindowText(hwnd))
            title = win32gui.GetWindowText(hwnd)
            if title.find(win_title) >= 0:
                print("句柄：：", hwnd, "标题：", win32gui.GetWindowText(hwnd))
                return hwnd

        print(f"没有找到对应标题的窗口{win_title}")
        return None

    def getWinRect(self,hwnd):
        rect = win32gui.GetWindowRect(hwnd)
        left, top, right, bot = rect
        w = right - left
        h = bot - top

        return {
            "left":left,
            "top":top,
            "right":right,
            "bot":bot,
            "width":w,
            "height":h,
        }

    def getScreen(self):
        # 获取桌面窗口句柄
        hWnd = win32gui.GetDesktopWindow()
        # 获取句柄窗口的大小信息
        left, top, right, bot = win32gui.GetWindowRect(hWnd)
        width = right - left
        height = bot - top
        # 返回句柄窗口的设备环境，覆盖整个窗口，包括非客户区，标题栏，菜单，边框
        hWndDC = win32gui.GetWindowDC(hWnd)
        # 创建设备描述表
        mfcDC = win32ui.CreateDCFromHandle(hWndDC)
        # 创建内存设备描述表
        saveDC = mfcDC.CreateCompatibleDC()
        # 创建位图对象准备保存图片
        saveBitMap = win32ui.CreateBitmap()
        # 为bitmap开辟存储空间
        saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
        # 将截图保存到saveBitMap中
        saveDC.SelectObject(saveBitMap)
        # 保存bitmap到内存设备描述表
        saveDC.BitBlt((0, 0), (width, height), mfcDC, (0, 0), win32con.SRCCOPY)

        ###获取位图信息   opencv+numpy保存
        signedIntsArray = saveBitMap.GetBitmapBits(True)
        im_opencv = numpy.frombuffer(signedIntsArray, dtype='uint8')
        im_opencv.shape = (height, width, 4)
        cv2.cvtColor(im_opencv, cv2.COLOR_BGRA2RGB)

        # cv2.imwrite("im_opencv.jpg",im_opencv,[int(cv2.IMWRITE_JPEG_QUALITY), 100]) #保存

        # 删除保存位图对象的句柄，释放内存
        win32gui.DeleteObject(saveBitMap.GetHandle())
        # 删除保存设备上下文的句柄，释放内存
        saveDC.DeleteDC()
        # 删除兼容设备上下文的句柄，释放内存
        mfcDC.DeleteDC()
        # 释放窗口设备上下文，释放内存
        win32gui.ReleaseDC(hWnd, hWndDC)

        return im_opencv


winapi = WindowsApi()
