# 图像识别模块（封装了屏幕识别、模板匹配、小地图朝向检测）
# magic_wow_automation/task_executor/image_detection.py
import cv2
from utils.WindowsApi import winapi
from ultralytics import YOLO
import time
import os
import datetime
import config.config

# === 新增：偏移缓存 ===
from utils.offset_cache import get_offset, upsert_offset

from task_executor.serial_operator import get_serial_controller

# 加载训练好的YOLOv8模型（路径根据实际情况调整）
model = YOLO("weights/best.pt")


def save_debug_image(img, folder="res/img", prefix="debug", boxes=None, class_names=None, confidences=None, threshold=0.2):
    """
    注意：现在只在“最终失败”时才会调用这个函数（见 detect_target 末尾）。
    不再在每次尝试中保存，避免成功时也落盘。
    """
    os.makedirs(folder, exist_ok=True)
    img_copy = img.copy()

    if boxes and class_names:
        for i, (box, cls_name) in enumerate(zip(boxes, class_names)):
            x1, y1, x2, y2 = map(int, box)
            conf = confidences[i] if confidences and i < len(confidences) else 1.0
            color = (0, 255, 0) if conf >= threshold else (0, 255, 255)  # green or yellow

            cv2.rectangle(img_copy, (x1, y1), (x2, y2), color, 2)
            label = f"{cls_name} {conf:.2f}"
            cv2.putText(img_copy, label, (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = os.path.join(folder, f"{prefix}_{timestamp}.jpg")
    cv2.imwrite(filename, img_copy, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    print(f"[调试截图] 已保存截图到 {filename}")


def _normalized_key(name: str) -> str:
    return name.lower().replace("-", "_").strip()


# === 新增：仅这些来自 JSON 的目标名才启用“偏移量缓存流程” ===
_JSON_IMAGE_KEYS_RAW = [
    "SHOPPING-BTN", "SEARCH-BTN", "EXPORT-RESULT-BTN", "LOAD-MORE-BTN", "TEXT-TO-COLUMN",
    "AUTO-TEXT-COLUMN", "AUTO-TEXT-COLUMN-CONFIRM-BTN",
    "CLICK-SAY-BTN", "DATA", "CONFIRM-INSERT-WORK-SHEET",
    "TAG-LINK-ICON", "BATTLE-LINK-ICON", "START-GAME-BTN",
    "SERVER-NAME", "SERVER-NAME-SELECTED",
    "BATTLE-PWD-INPUT", "RETURN-CHARACTER-SELECT", "CLOSE-WPS-FILE", "WPS-CREATE-FILE",
    "WPS-LINK-ACTIVATE-ICON", "SAVE-FILE-NAME-BTN",
    "SAVE-FILE-ICON", "WPS-CREATE-ICON", "WPS-LINK-ICON",
    "WPS-CREATE-TABLE", "WPS-FILE-ICON", "WOW-LINK-ICON", "CLICK-FOCUS-BTN", "CELL-COPY-LOCATION"
]
_CACHE_KEYS = { _normalized_key(k) for k in _JSON_IMAGE_KEYS_RAW }

sheet_count = None

# 储存sheet_name位置数组，作为保底用
SHEET_NAME_LOCATION_DATA = [(135, 1005), (213, 1005), (286, 1005), (364, 1005), (439, 1005), (515, 1005), (591, 1005), (667, 1005),
                            (743, 1005), (819, 1005), (895, 1005), (971, 1005), (1047, 1005)]
# 储存insert_work_sheet位置数组，作为保底用
INSERT_WORK_SHEET_LOCATION_DATA = [(222, 492), (300, 492), (373, 492), (451, 492), (526, 492), (602, 492), (678, 492), (754, 492),
                                   (830, 492), (906, 492), (982, 492), (1058, 492)]


def _sheet_name_fallback_pos(sheet_count: int):
    """根据 sheet 数返回保底坐标"""
    if sheet_count is None or sheet_count <= 0:
        return None
    if sheet_count <= len(SHEET_NAME_LOCATION_DATA):
        return SHEET_NAME_LOCATION_DATA[sheet_count - 1]
    return SHEET_NAME_LOCATION_DATA[-1]


def _apply_offset(pt, offset):
    return (int(pt[0] + offset[0]), int(pt[1] + offset[1]))


def _is_valid_point(pt):
    x, y = pt
    return isinstance(x, int) and isinstance(y, int) and (x != 0 or y != 0)


# —— 魔兽相关目标（使用偏移兜底前需确认在主页面）——
_WOW_RELATED_RAW = [
    "SHOPPING-BTN", "SEARCH-BTN", "EXPORT-RESULT-BTN", "LOAD-MORE-BTN",
    "CLICK-SAY-BTN", "RETURN-CHARACTER-SELECT", "CLICK-FOCUS-BTN"
]
WOW_RELATED_KEYS = { _normalized_key(k) for k in _WOW_RELATED_RAW }

# 放在文件顶部：哪些目标允许把偏移量写入数据库
_ALLOW_OFFSET_PERSIST = {}  # 仅此目标入库

# 主页面判定： (click_say_btn OR click_focus_btn) AND npc_name
# 说明：这里假设你的模型里有 "NPC-NAME" 这个类名；若你实际类名不同，请改成真实类名。
NPC_NAME_KEY = _normalized_key("NPC-NAME")
CLICK_SAY_KEY = _normalized_key("CLICK-SAY-BTN")
CLICK_FOCUS_KEY = _normalized_key("CLICK-FOCUS-BTN")


def _exists_class(results, normalized_key: str, threshold: float=0.5) -> bool:
    """在一次YOLO推理结果中，判断是否存在指定类别"""
    for r in results:
        for i, cls_id in enumerate(r.boxes.cls):
            cls_name = _normalized_key(r.names[int(cls_id)])
            conf = float(r.boxes.conf[i])
            if cls_name == normalized_key and conf >= threshold:
                return True
    return False


def _is_in_wow_mainpage(screenshot=None) -> bool:
    """
    判定是否在魔兽主页面：(CLICK-SAY-BTN 或 CLICK-FOCUS-BTN) 或 NPC-NAME。
    只做一次YOLO推理，避免多次抓屏。
    """
    frame = screenshot if screenshot is not None else winapi.getScreen()
    results = model(frame)
    has_click = _exists_class(results, CLICK_SAY_KEY, 0.4) or _exists_class(results, CLICK_FOCUS_KEY, 0.4)
    has_npc   = _exists_class(results, NPC_NAME_KEY, 0.4)
    return has_click or has_npc


# —— 必须达到更高置信度阈值的图片（标准化后名字：lower + '-'→'_'）——
_STRICT_CONF_KEYS = {
    'npc_character', 'npc_name', 'auto_text_column'
}

# 统一严格阈值（当某图片在 _STRICT_CONF_KEYS 里，但未在字典里单独配置时使用）
STRICT_CONF_DEFAULT = 0.85

# 可选：为部分图片单独设阈值（优先级高于 STRICT_CONF_DEFAULT）
STRICT_CONF_PER_IMAGE = {}


# === 新增：虚拟机页面判定相关 ===
VM_PAGE_ICON_1 = _normalized_key("WPS-LINK-ICON")
VM_PAGE_ICON_2 = _normalized_key("WPS-LINK-ACTIVATE-ICON")


def _exists_any(results, normalized_keys: set, threshold: float = 0.40) -> bool:
    for r in results:
        for i, cls_id in enumerate(r.boxes.cls):
            cls_name = _normalized_key(r.names[int(cls_id)])
            conf = float(r.boxes.conf[i])
            if cls_name in normalized_keys and conf >= threshold:
                return True
    return False


def _is_in_vm_page(screenshot=None, threshold: float = 0.40, max_attempts: int = 3, interval: float = 0.5) -> bool:
    """
    尝试多次（默认 3 次）检测 {WPS-LINK-ICON, WPS-LINK-ACTIVATE-ICON} 是否存在，
    只要有一次识别到，就认为当前在虚拟机页面。
    """
    for attempt in range(1, max_attempts + 1):
        frame = screenshot if (screenshot is not None and attempt == 1) else winapi.getScreen()
        results = model(frame)

        if _exists_any(results, {VM_PAGE_ICON_1, VM_PAGE_ICON_2}, threshold):
            print(f"[VM页面判定] 第 {attempt} 次检测到虚拟机图标 → 在虚拟机页面")
            return True
        else:
            print(f"[VM页面判定] 第 {attempt} 次未检测到虚拟机图标")
            if attempt < max_attempts:
                time.sleep(interval)

    print("[VM页面判定] 多次检测均未发现虚拟机图标 → 不在虚拟机页面")
    return False


def _click_recover_to_vm(vm_index: int = 0):
    """
    使用串口控制器点击一个安全的屏幕位置以切回虚拟机页面。
    优先读取 config.config.VM_RECOVER_CLICK_POS[vm_index]，否则采用兜底坐标。
    """
    try:
        recover_pos_list = getattr(config.config, "VM_RECOVER_CLICK_POS", None)
        if isinstance(recover_pos_list, (list, tuple)) and len(recover_pos_list) > vm_index:
            rx, ry = recover_pos_list[vm_index]
        else:
            # 兜底坐标（例如VMware标签栏左上角）
            rx, ry = 120, 50

        controller = get_serial_controller()

        # ==== 先移动到目标位置 ====
        controller.move_mouse_abs(rx, ry)
        print(f"[恢复点击] 鼠标已移动到 ({rx}, {ry})，准备点击")
        time.sleep(2)  # 停留 2 秒

        # ==== 点击 ====
        controller.click_mouse()
        print(f"[恢复点击] 已点击以切回虚拟机页面: ({rx}, {ry})")

        time.sleep(0.8)  # 给界面一点切换时间

    except Exception as e:
        print(f"[恢复点击异常] {e}")


def detect_target(target_name, max_attempts=5, interval=5, vm_index=0, task_type=None, _allow_recover_retry=True):
    """
    使用YOLOv8识别目标，返回匹配目标中置信度最高的坐标。

    新策略：
      1) 不再先查DB偏移量；直接跑识别。
      2) 若（标准/保底）识别成功：
           - 直接返回坐标；
           - 若目标在白名单中，则把坐标写入/更新 DB 偏移量（便于下次失败兜底）。
      3) 若识别最终失败：
           - 若目标在白名单中，尝试从DB读取偏移量作为兜底；命中则返回偏移量；
           - 否则返回失败（并仅在这里落盘一次调试截图）。
    """
    screenshot = None
    normalized_target_name = _normalized_key(target_name)

    def _required_conf_for(name: str, base: float) -> float:
        """返回该目标的最终置信度阈值：若在严格数组里，则用更高阈值"""
        if name in _STRICT_CONF_KEYS:
            return STRICT_CONF_PER_IMAGE.get(name, STRICT_CONF_DEFAULT)
        return base

    # ==== 阈值设置 ====
    DEFAULT_THRESHOLD = 0.6
    SPECIAL_CONF_THRESHOLDS = {
        "insert_work_sheet": 0.3,
        "sheet_name": 0.3
    }
    ALLOW_LOW_CONF_TARGETS = {"cell_copy_location", "auto_text_column"}
    LOW_CONFIDENCE_THRESHOLD = 0.01

    initial_threshold = SPECIAL_CONF_THRESHOLDS.get(normalized_target_name, DEFAULT_THRESHOLD)

    # 计算该目标最终阈值（可能比 initial_threshold 高）
    required_conf = _required_conf_for(normalized_target_name, initial_threshold)

    # 白名单：仅这些目标才参与“偏移量入库 + 失败兜底读取偏移量”
    use_cache_flow = normalized_target_name in _CACHE_KEYS

    # 当前上下文（用于偏移量唯一键）
    vm_tag = '1'
    screen_w = 1650
    screen_h = 962

    best_pos = None
    best_conf = 0.0
    tried_attempts = 0

    # 仅在最终失败时保存一次调试图
    last_boxes, last_names, last_confs, last_frame = None, None, None, None

    # ========== 第一阶段：标准识别 ==========
    for attempt in range(1, max_attempts + 1):
        screenshot = winapi.getScreen()  # 仅内存抓屏，不落盘
        results = model(screenshot)
        tried_attempts += 1

        all_boxes, all_names, all_confs = [], [], []

        for r in results:
            for i, cls_id in enumerate(r.boxes.cls):
                class_name = r.names[int(cls_id)]
                conf = float(r.boxes.conf[i])
                box = r.boxes.xyxy[i].cpu().numpy()

                all_boxes.append(box)
                all_names.append(class_name)
                all_confs.append(conf)

                normalized_class_name = _normalized_key(class_name)

                if normalized_class_name == normalized_target_name and conf >= required_conf:
                    x1, y1, x2, y2 = box
                    center_x = int((x1 + x2) / 2)
                    center_y = int((y1 + y2) / 2)
                    print(f"[标准识别成功] 第 {attempt} 次识别到 {class_name} at ({center_x}, {center_y}), 置信度 {conf:.2f}，阈值 {required_conf:.2f}")

                    if conf > best_conf:
                        best_conf = conf
                        best_pos = (center_x, center_y)

        last_boxes, last_names, last_confs, last_frame = all_boxes, all_names, all_confs, screenshot

        if best_pos:
            # —— 如果这次识别的是 sheet_name，缓存本 VM 的 sheet_name 坐标，供 insert_work_sheet 兜底使用 ——
            if normalized_target_name == 'sheet_name':
                config.config.CURRENT_VM_SHEETNAME_LOCATION[vm_index] = (int(best_pos[0]), int(best_pos[1]))

            if normalized_target_name == 'shopping_btn':
                config.config.shopping_btn_related_obj[vm_index] = False
            elif normalized_target_name == 'search_btn':
                config.config.search_btn_related_obj[vm_index] = False
            # 白名单：识别成功后写库，供未来失败兜底使用
            if use_cache_flow and normalized_target_name in _ALLOW_OFFSET_PERSIST:
                try:
                    image_key_name = 'cell_copy_location' if config.config.is_first_cell_obj[vm_index] else 'cell_copy_location_2'
                    upsert_offset(
                        image_key=image_key_name,
                        offset_x=int(best_pos[0]),
                        offset_y=int(best_pos[1]),
                        vm_tag=vm_tag,
                        screen_w=screen_w,
                        screen_h=screen_h,
                        confidence=float(best_conf) if best_conf else None,
                        source="auto"
                    )
                except Exception as e:
                    print(f"[偏移入库失败] {e}")
            return True, best_pos, None

        print(f"[标准识别失败] 第 {attempt} 次未找到目标: {target_name}")
        if attempt < max_attempts:
            time.sleep(interval)

    # ========== 第二阶段：保底识别（仅对显式允许的目标）==========
    if normalized_target_name in ALLOW_LOW_CONF_TARGETS:
        if normalized_target_name in _STRICT_CONF_KEYS:
            print("[保底跳过] 严格阈值目标不使用低置信度保底")
        else:
            print(f"[保底识别] 启动低置信度容错匹配机制: {target_name}")
            for attempt in range(1, max_attempts + 1):
                screenshot = winapi.getScreen()
                results = model(screenshot)
                tried_attempts += 1

                all_boxes, all_names, all_confs = [], [], []

                for r in results:
                    for i, cls_id in enumerate(r.boxes.cls):
                        class_name = r.names[int(cls_id)]
                        conf = float(r.boxes.conf[i])
                        box = r.boxes.xyxy[i].cpu().numpy()

                        all_boxes.append(box)
                        all_names.append(class_name)
                        all_confs.append(conf)

                        normalized_class_name = _normalized_key(class_name)

                        if normalized_class_name == normalized_target_name and conf >= LOW_CONFIDENCE_THRESHOLD:
                            x1, y1, x2, y2 = box
                            center_x = int((x1 + x2) / 2)
                            center_y = int((y1 + y2) / 2)
                            print(f"[保底识别成功] 第 {attempt} 次宽松识别 {class_name} at ({center_x}, {center_y}), 置信度 {conf:.2f}")

                            if use_cache_flow and normalized_target_name in _ALLOW_OFFSET_PERSIST:
                                try:
                                    upsert_offset(
                                        image_key=normalized_target_name,
                                        offset_x=int(center_x),
                                        offset_y=int(center_y),
                                        vm_tag=vm_tag,
                                        screen_w=screen_w,
                                        screen_h=screen_h,
                                        confidence=float(conf),
                                        source="auto"
                                    )
                                except Exception as e:
                                    print(f"[偏移入库失败] {e}")

                            return True, (center_x, center_y), None

                last_boxes, last_names, last_confs, last_frame = all_boxes, all_names, all_confs, screenshot

                print(f"[保底识别失败] 第 {attempt} 次仍未找到目标: {target_name}")
                if attempt < max_attempts:
                    time.sleep(interval)

    # ========== 识别最终失败：仅此时保存调试图 & 白名单走偏移兜底 ==========
    print(f"[最终失败] 共 {tried_attempts} 次尝试均未识别到目标: {target_name}")
    if last_frame is not None:
        save_debug_image(
            last_frame,
            prefix=f"detect_fail_{target_name}",
            boxes=last_boxes,
            class_names=last_names,
            confidences=last_confs,
            threshold=0.2
        )

    # === 新增：最终失败后，判断是否处于虚拟机页面；若不在则恢复并重试一次 ===
    try:
        # 复用最后一帧，避免重复抓屏；若没有则抓一次
        frame_for_vm_check = last_frame if last_frame is not None else winapi.getScreen()
        in_vm = _is_in_vm_page(frame_for_vm_check)
        print(f"[VM页面判定] 当前是否在虚拟机页面: {in_vm}")
        if (not in_vm) and _allow_recover_retry:
            print("[VM页面判定] 不在虚拟机页面 -> 执行恢复点击并重试上次识别")
            _click_recover_to_vm(vm_index=vm_index)
            # 恢复后仅重试一次，避免死循环
            return detect_target(
                target_name,
                max_attempts=max_attempts,
                interval=interval,
                vm_index=vm_index,
                task_type=task_type,
                _allow_recover_retry=False
            )
    except Exception as e:
        print(f"[VM页面判定/恢复] 异常: {e}")

    if task_type == 'recreate_wps' or task_type == 'paste_auction_data':
        if normalized_target_name == "confirm_insert_work_sheet":
            return False, None, None

    if task_type == 'has_wow_white_page':
        return False, None, None

    if task_type == 'is_detected_create_file':
        return False, None, None

    if task_type == 'is_detected_data':
        return False, None, None

    if task_type == 'is_wow_frozen':
        return False, None, None

    # —— 特殊保底：sheet_name 用数组 + 数据库记录的 sheet 数 ——
    if normalized_target_name == "sheet_name":
        try:
            from utils.task_state import get_sheet_count, get_insertting_sheet  # 见第②部分
            sheet_count = get_sheet_count(vm_id=int(vm_index), task_name='save_sheet_count', task_date=config.config.CURRENT_DAY)  # vm_tag如果是字符串就转成int
            is_insertting_sheet = get_insertting_sheet(vm_id=int(vm_index), task_name='save_insertting_sheet', task_date=config.config.CURRENT_DAY)
        except Exception as e:
            print(f"[sheet保底] 读取sheet_count失败: {e}")
            sheet_count = None
            is_insertting_sheet = None

        if not sheet_count:
            param_sheet_count = 1
        else:
            if sheet_count < 12:
                if is_insertting_sheet:
                    param_sheet_count = sheet_count + 1
                else:
                    param_sheet_count = sheet_count
            else:
                param_sheet_count = 12

        fb = _sheet_name_fallback_pos(param_sheet_count)
        config.config.CURRENT_VM_SHEETNAME_LOCATION[vm_index] = (int(fb[0]), int(fb[1]))
        if fb:
            print(f"[sheet保底命中] sheet_count={param_sheet_count} -> pos={fb}")
            return True, fb, None
        else:
            print("[sheet保底] 无有效sheet_count，放弃")

    # 保底返回
    if normalized_target_name == "insert_work_sheet":
        fb = _apply_offset(config.config.CURRENT_VM_SHEETNAME_LOCATION[vm_index], config.config.INSERT_WORK_SHEET_OFFSET)
        print(f"[insert_ws 底] pos={fb} offset={config.config.INSERT_WORK_SHEET_OFFSET}")
        return True, fb, None

    # —— 白名单目标：尝试偏移兜底（魔兽相关需先判定是否在主页面）——
    if use_cache_flow:
        offset_key_name = None
        if normalized_target_name == 'cell_copy_location':
            if not config.config.is_first_cell_obj[vm_index]:
                offset_key_name = 'cell_copy_location_2'
        else:
            offset_key_name = normalized_target_name

        cached = get_offset(offset_key_name, vm_tag, screen_w, screen_h)
        print(f"{normalized_target_name}查询是否在偏移表中：{cached}")
        if cached:
            print("进入兜底命中偏移")
            if normalized_target_name in WOW_RELATED_KEYS:
                # 魔兽相关：兜底前先确认在主页面，否则认为掉线/不在场景，直接失败
                # 复用最后一次截图以减少抓屏；若没有则再抓一次
                frame_for_check = last_frame if last_frame is not None else winapi.getScreen()
                if not _is_in_wow_mainpage(frame_for_check):
                    print(f"[兜底被拒] 当前不在魔兽主页面，忽略偏移量。target={target_name}")
                    return False, None, True
            print(f"[兜底命中偏移] {target_name} -> {cached} (vm={vm_tag}, {screen_w}x{screen_h})")
            if normalized_target_name == 'shopping_btn':
                config.config.shopping_btn_related_obj[vm_index] = True
            elif normalized_target_name == 'search_btn':
                config.config.search_btn_related_obj[vm_index] = True
            return True, cached, None

    return False, None, None
