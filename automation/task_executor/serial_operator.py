# magic_wow_automation/task_executor/serial_operator.py

import threading
import time
import serial
import atexit
import ch9329Comm
from utils.log import logger

USE_HARDWARE_MOUSE = True
_serial_controller_instance = None


class SerialController:
    def __init__(self, port='COM3', baudrate=115200):
        try:
            self.ser = serial.Serial(port, baudrate)
            self.keyboard = ch9329Comm.keyboard.DataComm()
            self.mouse = ch9329Comm.mouse.DataComm(screen_width=1920, screen_height=1080)
            logger.info(f"串口 {port} 已打开，波特率 {baudrate}")
        except Exception as e:
            logger.error(f"串口初始化失败：{e}")

    def release(self):
        """
        主动发送零数据包，释放所有按键
        """
        try:
            HEAD = b'\x57\xAB'
            ADDR = b'\x00'
            CMD = b'\x02'
            LEN = b'\x08'
            DATA = b'\x00' * 8

            checksum = (
                sum(HEAD) + int.from_bytes(ADDR, 'big') +
                int.from_bytes(CMD, 'big') + int.from_bytes(LEN, 'big') +
                sum(DATA)
            ) % 256

            packet = HEAD + ADDR + CMD + LEN + DATA + bytes([checksum])
            self.ser.write(packet)
            logger.info("释放按键：发送全 0 零包完成")
        except Exception as e:
            logger.error(f"发送释放命令失败：{e}")

    def press_keys(self, keys: str):
        """
        输入键串，每两个字符表示一个键码，如 AA 表示 A，33 表示 3。
        自动在 10 秒后触发 release，无论是否成功。
        """
        def auto_release():
            time.sleep(5)
            logger.info("超过5秒，自动释放所有按键")
            self.release()

        threading.Thread(target=auto_release, daemon=True).start()

        try:
            logger.info(f"发送按键：{keys}")
            MAX_KEYS = 6
            if len(keys) % 2 != 0:
                logger.error("输入格式错误：必须成对字符")
                return

            # 添加这行，用于打印人类可读的字符
            typed_password = ""

            total_pairs = len(keys) // 2

            for start in range(0, total_pairs, MAX_KEYS):
                batch = keys[start * 2: (start + MAX_KEYS) * 2]

                for i in range(0, len(batch), 2):
                    pair = batch[i:i + 2]
                    if not pair.isalnum():
                        logger.warning(f"跳过无效对: {pair}")
                        continue

                    if pair.isalpha() and pair.isupper():
                        typed_password += pair[0].lower()  # 代表小写
                        self.keyboard.send_data(pair, port=self)
                        logger.info(f"输入小写字母：{pair}")
                    else:
                        typed_password += pair[0]  # 数字或大写
                        self.keyboard.send_data(pair, port=self)
                        logger.info(f"输入字符：{pair}")

                    time.sleep(0.05)
                    self.release()
                    time.sleep(0.05)

            # 添加：输出最终识别的密码字符串
            logger.info(f"本次输入内容：{typed_password}")

            logger.info("全部输入完成")
        except Exception as e:
            logger.error(f"发送失败：{e}")
            self.release()

    def send_shift_tap(self, hold: float = 0.05):
        """
        点按一次 SHIFT（按下→保持→松开）
        """
        # 按下 Shift
        self.send_data('', ctrl='L_SHIFT', port=self)
        time.sleep(hold)
        # 松开 Shift
        self.send_data('', ctrl='', port=self)

    def send_ctrl_key(self, normal_key: str, ctrl_key: str = "L_CTRL"):
        """
        发送组合键，如 Ctrl + C、Ctrl + V、Ctrl + Down 等。

        参数:
            normal_key (str): 普通按键的键码，如 "CC", "VV", "DOWN"（须存在于 normal_button_hex_dict 中）
            ctrl_key (str): 控制键，默认是 L_CTRL
        """
        try:
            logger.info(f"发送组合键：{ctrl_key} + {normal_key}")
            self.keyboard.send_data(normal_key, ctrl=ctrl_key, port=self)
            time.sleep(0.5)
            self.release()
            logger.info(f"发送组合键完成：{ctrl_key} + {normal_key}")
        except Exception as e:
            logger.error(f"发送组合键失败：{ctrl_key} + {normal_key}，错误：{e}")
            self.release()

    def send_single_key(self, key_code_str: str):
        """
        发送单个按键（如 ESC、Enter），支持关键词或2字符键码。
        """
        try:
            logger.info(f"发送单个按键：{key_code_str}")

            # 关键词映射到2位键码
            key_mapping = {
                'ESC': '29',
                'DOWN': '51',
                'ENTER': '28'
                # 可扩展更多...
            }

            key_code = key_mapping.get(key_code_str, key_code_str)  # 支持直接传入'29'这种

            self.keyboard.send_data(key_code, port=self)
            self.release()
        except Exception as e:
            logger.error(f"发送单个按键失败：{e}")
            self.release()

    def move_mouse_abs(self, x, y):
        try:
            logger.info(f"串口鼠标移动到: ({x},{y})")
            self.mouse.send_data_absolute(x, y, ctrl='', port=self)
        except Exception as e:
            logger.error(f"串口鼠标移动失败：{e}")

    def mouse_down(self, button='left'):
        try:
            logger.info(f"鼠标按下: {button}")
            ctrl = 'LE' if button == 'left' else 'RI'
            self.mouse.send_data_relatively(0, 0, ctrl=ctrl, port=self)
        except Exception as e:
            logger.error(f"鼠标按下失败：{e}")

    def mouse_up(self, button='left'):
        try:
            logger.info(f"鼠标释放: {button}")
            self.mouse.send_data_relatively(0, 0, ctrl='NU', port=self)
        except Exception as e:
            logger.error(f"鼠标释放失败：{e}")

    def click_mouse(self, button='left'):
        try:
            logger.info(f"鼠标单击: {button}")
            if button == 'left':
                self.mouse.click(port=self)
            elif button == 'right':
                self.mouse.send_data_relatively(0, 0, 'RI', port=self)
                time.sleep(0.2)
                self.mouse.send_data_relatively(0, 0, 'NU', port=self)
            else:
                logger.warning("不支持的鼠标按钮")
        except Exception as e:
            logger.error(f"鼠标单击失败：{e}")

    def double_click_mouse(self, button='left'):
        try:
            logger.info(f"鼠标双击: {button}")
            self.click_mouse(button)
            time.sleep(0.05)
            self.click_mouse(button)
            time.sleep(0.2)  # 给 UI 稳定响应时间
        except Exception as e:
            logger.error(f"鼠标双击失败：{e}")

    def move_and_click(self, x, y, button='left'):
        self.move_mouse_abs(x, y)
        time.sleep(0.05)
        self.click_mouse(button)

    def move_and_double_click(self, x, y, button='left'):
        self.move_mouse_abs(x, y)
        time.sleep(0.05)
        self.double_click_mouse(button)

    def drag_mouse(self, x1, y1, x2, y2, duration=0.5, button='left'):
        try:
            logger.info(f"开始拖动鼠标: ({x1},{y1}) -> ({x2},{y2})")
            self.move_mouse_abs(x1, y1)
            time.sleep(0.05)
            self.mouse_down(button)

            dx = x2 - x1
            dy = y2 - y1
            steps = int(duration / 0.01)
            for i in range(steps):
                ix = x1 + dx * i // steps
                iy = y1 + dy * i // steps
                self.mouse.send_data_absolute(ix, iy, ctrl=button, port=self)
                time.sleep(0.01)

            self.move_mouse_abs(x2, y2)
            self.mouse_up(button)
            logger.info("结束拖动")
        except Exception as e:
            logger.error(f"鼠标拖动失败：{e}")

    def scroll_mouse(self, amount: int = 1):
        try:
            logger.info(f"鼠标滚轮滚动: {amount}")
            for _ in range(abs(amount)):
                wheel = amount if amount > 0 else (0x100 + amount)
                HEAD = b'\x57\xAB'
                ADDR = b'\x00'
                CMD = b'\x05'
                LEN = b'\x05'
                DATA = bytearray([0x01, 0x00, 0x00, 0x00, wheel & 0xFF])
                SUM = (sum(HEAD) + int.from_bytes(ADDR, 'big') +
                       int.from_bytes(CMD, 'big') + int.from_bytes(LEN, 'big') +
                       sum(DATA)) % 256
                packet = HEAD + ADDR + CMD + LEN + DATA + bytes([SUM])
                self.ser.write(packet)
                time.sleep(0.05)
        except Exception as e:
            logger.error(f"鼠标滚轮滚动失败：{e}")

    def right_click_mouse(self):
        self.click_mouse(button='right')

    def close(self):
        try:
            self.ser.close()
            logger.info("串口已关闭")
        except Exception as e:
            logger.error(f"串口关闭失败：{e}")


def get_serial_controller():
    global _serial_controller_instance
    if _serial_controller_instance is None:
        _serial_controller_instance = SerialController()
        # 注册退出自动关闭串口
        atexit.register(_serial_controller_instance.close)
    return _serial_controller_instance
