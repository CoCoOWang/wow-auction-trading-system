from utils.db import log_task_execution, get_db_connection
from utils.log import logger
from task_executor.script_manager import get_task_script
from task_executor.image_detection import detect_target, _is_in_wow_mainpage
from task_executor.mouse_keyboard_action import execute_action
import time
from task_executor import serial_operator
from scheduler.special_task import start_click_say_btn_timer, start_relink_battle_timer
import config.config
from task_executor.task_chain import relink_battle_task, quit_and_login_wow_task
from utils.task_state import start_task, set_sheet_count, get_sheet_count, update_insertting_sheet, update_updating_sheet_content


def skip_condition(task):
    """
    判断任务是否可跳过（如今日已完成 + 非强制）
    """
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) AS cnt
                FROM task_execution_log
                WHERE task_type = %s AND quadrant = %s AND status = 'done' AND DATE(executed_at) = CURDATE()
            """, (task['type'], task['target_quadrant']))
            result = cursor.fetchone()
            if result["cnt"] > 0 and not task.get("required", False):
                return True
    finally:
        conn.close()
    return False


def smart_delay_with_detect_arr_img(task, i, steps, vm_index):
    step = steps[i]
    delay_time = step.get("delay", 1)
    logger.info(f"[延迟等待] {delay_time}s")

    next_step = steps[i + 1] if i + 1 < len(steps) else None
    if delay_time > 10 and next_step and next_step.get("action") == "detect_arr_img":
        target_list = next_step.get("target_image_arr", [])
        step_num_list = next_step.get("jump_step_num", [])
        is_select_all = next_step.get("is_select_all", False)
        image_arr_index = next_step.get("image_arr_index", 0)
        matched_name = None
        matched_pos = None
        matched_results = []

        logger.info("[智能延迟] 启动提前识别 detect_arr_img 图标")
        interval = 1
        elapsed = 0
        is_wow_whitepage = False

        while elapsed < delay_time:
            for target_name in target_list:
                base_name = target_name.split('.')[0]
                current_type = None
                if image_arr_index == 200:
                    current_type = 'has_wow_white_page'
                elif image_arr_index == 300:
                    current_type = 'is_detected_create_file'
                elif image_arr_index == 400:
                    current_type = 'is_detected_data'
                found, pos, offline_status = detect_target(base_name, max_attempts=3, interval=1, vm_index=vm_index, task_type=current_type)
                if found:
                    logger.info(f"[提前识别成功] {base_name} @ {pos}")
                    # npc_name 特殊处理：向下偏移 20 像素
                    if base_name == "npc_name":
                        pos = (pos[0], pos[1] + 20)
                    if is_select_all:
                        matched_results.append(base_name)
                        if base_name == 'copy_text_closed_btn':
                            matched_pos = pos
                    else:
                        matched_name = base_name
                        matched_pos = pos
                        break
                else:
                    if image_arr_index == 200:
                        is_wow_whitepage = True
            if is_select_all:
                if len(matched_results) > 0:
                    break
            else:
                if matched_name:
                    break
            time.sleep(interval)
            elapsed += interval

        if matched_name:
            task["extra"]["last_detect_pos"] = {"x": matched_pos[0], "y": matched_pos[1]}
            task["extra"]["matched_image_name"] = matched_name
            step_num_index = target_list.index(matched_name + ".png")
            task["extra"]["matched_image_index"] = step_num_index
            step_num = step_num_list[step_num_index]

            if not serial_operator.USE_HARDWARE_MOUSE or next_step.get("is_need_click"):
                execute_action(matched_pos[0], matched_pos[1], click_times=1)

            if matched_name:
                logger.info(f"已经识别到{matched_name}，跳过{step_num}步")
                i += step_num

            task["step_index"] = i
            return i, True, None
        elif len(matched_results) > 0:
            if "export_all_data" in matched_results:
                step_num = step_num_list[0]
                logger.info(f"已经识别到export_all_data，跳过{step_num}步")
                i += step_num
                logger.info("本次全部复制粘贴完成！！！")
                task["extra"]["max_step_index"] = 12
                config.config.HAS_EXPORT_ALL_DATA[vm_index] = True
            elif "copy_text_closed_btn" in matched_results:
                if image_arr_index == 200 and is_wow_whitepage:
                    logger.info(f"已经识别到WOW白屏，复制回退")
                    i = 1
                elif image_arr_index == 200:
                    step_num = step_num_list[0]
                    logger.info("未识别到WOW白屏")
                    i += step_num
                else:
                    step_num = step_num_list[0]
                    logger.info(f"已经识别到copy_text_closed_btn，跳过{step_num}步")
                    i += step_num
                    task["extra"]["max_step_index"] = 13

            if matched_pos:
                task["extra"]["last_detect_pos"] = {"x": matched_pos[0], "y": matched_pos[1]}

            task["step_index"] = i
            if image_arr_index == 200:
                return  i, True, None
            return i, True, task["extra"]["max_step_index"]
        else:
            if image_arr_index == 300:
                i -= 3
                task["step_index"] = i
                return i, True, None
            logger.info("[智能延迟] 未提前识别成功，正常等待")
            time.sleep(delay_time)
            i += 1
            task["step_index"] = i
            return i, True, None
    else:
        time.sleep(delay_time)
        i += 1
        task["step_index"] = i
        return i, True, None


def execute_task(task, vm_index):
    task_id = task["id"]
    task_type = task["type"]
    quadrant = task["target_quadrant"]
    step_index = task.get("step_index", 0)
    max_index = task.get("extra", {}).get("max_step_index", None)

    if skip_condition(task):
        log_task_execution(task_id, task_type, quadrant, "skipped", "今日已完成，跳过", step_index)
        return True

    try:
        script = get_task_script(task_type)
        if not script:
            raise Exception("任务脚本不存在")

        i = step_index

        steps = script['steps']
        while i < len(steps):
            if max_index is not None and i > max_index:
                logger.info(f"[调试跳出] 已超过最大执行步骤 index={max_index}，提前结束任务")
                break
            step = steps[i]
            action = step['action']
            logger.info(f"[执行] {task_type} 步骤[{i}]: {step['description']}")

            if action == 'delay':
                # time.sleep(step.get("delay", 1))
                i, jumped, delay_max_index = smart_delay_with_detect_arr_img(task, i, steps, vm_index)
                if delay_max_index:
                    max_index = delay_max_index
                if jumped:
                    continue  # 提前识别成功并跳转后续步骤

            if action == 'escape' or action == 'send_escape_three_times':
                if not execute_action(None, None, action, click_times=3 if action == 'send_escape_three_times' else 1, click_interval=1):
                    # log_task_execution(task_id, task_type, quadrant, "failed", "点击失败", i)
                    logger.info(f"ESC失败")
                    return False

                if action == 'send_escape_three_times':
                    config.config.HAS_EXPORT_ALL_DATA[vm_index] = False
                    config.config.IS_RELOGIN_WOW_FLG[vm_index] = True

            if action == 'enter':
                sheet_count = get_sheet_count(vm_index, 'save_sheet_count', config.config.CURRENT_DAY)
                set_sheet_count(vm_index, (sheet_count + 1) if sheet_count else 1, 'save_sheet_count', config.config.CURRENT_DAY)
                update_insertting_sheet(vm_id=vm_index, task_name='save_insertting_sheet', is_insertting_sheet=0, task_date=config.config.CURRENT_DAY)
                update_updating_sheet_content(vm_id=vm_index, task_name='update_sheet_content', is_updating_sheet_content=1, task_date=config.config.CURRENT_DAY)
                if not execute_action(None, None, action):
                    logger.info(f"Enter失败")
                    return False
                # 发送CTRL+S
                if not execute_action(None, None, action='ctrl_s'):
                    logger.info("CTRL+S输入失败")
                    return False
                logger.info("保存WPS文件成功")

            elif action == 'detect':
                target_name = step['target_image'].split('.')[0]
                is_need_click = step['is_need_click']
                found, pos, offline_status = detect_target(target_name, max_attempts=3, interval=2, vm_index=vm_index, task_type=task_type if task_type=='recreate_wps' or (task_type=='paste_auction_data' and not is_need_click) else None)
                if not found:
                    if offline_status:
                        logger.info("图像识别失败，判断是掉线状态")
                        config.config.WOW_OFFLINE_STATUS[vm_index] = True
                        config.config.SPECIAL_TASK_ACTIVE[vm_index] = False
                        return True
                    logger.info(f"识别失败: {target_name}")
                    if target_name == 'loading_item_info':
                        logger.info(f"[特殊任务] VM{vm_index + 1} 检测不到 LOADING-ITEM-INFO，结束定时点击")
                        config.config.SPECIAL_TASK_ACTIVE[vm_index] = False
                        task["step_index"] = i + 1
                        i += 1
                        continue
                    elif target_name == 'data_activate':
                        task["step_index"] = i + 1
                        i += 1
                        continue
                    if task_type == 'quit_wow':
                        if target_name == 'wps_link_activate_icon':
                            task["step_index"] = i + 1
                            i += 1
                            continue
                    elif task_type == 'recreate_wps':
                        if target_name == 'confirm_insert_work_sheet':
                            task["step_index"] = i + 1
                            i += 1
                            continue
                    elif task_type == 'paste_auction_data' and not is_need_click:
                        if target_name == 'confirm_insert_work_sheet':
                            task["step_index"] = i + 1
                            i += 1
                            continue
                    elif task_type == 'reopen_wow_then_close_window':
                        if target_name == 'copy_text_closed_btn':
                            return True
                    return False

                # 立即点击识别到的位置作为“确认”
                click_x, click_y = pos

                if not serial_operator.USE_HARDWARE_MOUSE or step['is_need_click']:
                    logger.info(f"[识别点击] 点击 {target_name} 位置以确认")
                    if not execute_action(click_x, click_y, click_times=1, click_interval=0.3):
                        logger.info(f"识别点击失败: {target_name}")
                        return False

                # 判断第一个sheet页的时候，sheet_name是否正确输入
                if target_name == 'cell_copy_location' and config.config.is_first_cell_obj[vm_index]:
                    if int(click_y) > 230:
                        logger.info("出现了sheet_name输入出错的情况，现在纠正")
                        # 发送CTRL+Z
                        if not execute_action(None, None, action='ctrl_z'):
                            logger.info("CTRL+Z输入失败")
                            return False
                        sheet_count = get_sheet_count(vm_index, 'save_sheet_count', config.config.CURRENT_DAY)
                        set_sheet_count(vm_index, (sheet_count - 1) if sheet_count > 1 else 1, 'save_sheet_count', config.config.CURRENT_DAY)
                        update_insertting_sheet(vm_id=vm_index, task_name='save_insertting_sheet',
                                                is_insertting_sheet=1, task_date=config.config.CURRENT_DAY)
                        task["step_index"] = i - 10
                        i -= 10
                        continue

                task["extra"]["last_detect_pos"] = {"x": click_x, "y": click_y}
                logger.info(f"识别成功: {target_name}")

                if target_name == "load_more_btn":
                    start_click_say_btn_timer(quadrant)
                elif target_name == "data_activate":
                    task["step_index"] = i + 2
                    i += 2
                    continue
                elif target_name == "save_file_name_btn":
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    config.config.CURRENT_DAY = today_str
                    # 插入或更新新建WPS表任务状态
                    start_task(vm_index, 'save_file', today_str)
                elif target_name == "search_btn":
                    if config.config.shopping_btn_related_obj[vm_index] and config.config.search_btn_related_obj[vm_index]:
                        task["step_index"] = 0
                        i = 0
                        continue
                elif target_name == "sheet_name":
                    config.config.is_show_excel_obj[vm_index] = True

                if task_type == 'prevent_afk_click':
                    if target_name == 'loading_item_info':
                        task["step_index"] = i + 2
                        i += 2
                        continue
                    elif target_name == 'export_result_btn':
                        if not execute_action(click_x, click_y, click_times=1, click_interval=0.3):
                            logger.info(f"点击鼠标失败: {target_name}")
                            return False

                if task_type == 'recreate_wps':
                    if target_name == 'confirm_insert_work_sheet':
                        config.config.is_show_excel_obj[vm_index] = False

                if task_type == 'paste_auction_data':
                    if target_name == 'confirm_insert_work_sheet':
                        if is_need_click:
                            config.config.is_first_cell_obj[vm_index] = True
                            update_insertting_sheet(vm_id=vm_index, task_name='save_insertting_sheet', is_insertting_sheet=1, task_date=config.config.CURRENT_DAY)
                        else:
                            # 点击取消按钮
                            if not execute_action(click_x + 82, click_y, action='click', click_times=1, click_interval=1):
                                # log_task_execution(task_id, task_type, quadrant, "failed", "点击失败", i)
                                logger.info(f"点击失败")
                                return False
                            logger.info("点击单元格内有其他内容的取消按钮")
                            # 发送CTRL+Z
                            if not execute_action(None, None, action='ctrl_z'):
                                logger.info("CTRL+Z输入失败")
                                return False
                            logger.info("回退错误的位置的粘贴")
                            # 发送CTRL+DOWN+DOWN
                            config.config.is_first_cell_obj[vm_index] = False
                            if not execute_action(None, None, action='ctrl_down'):
                                logger.info("CTRL+DOWN输入失败")
                                return False
                            logger.info("恢复错误粘贴后，继续CTRL+DOWN")
                            task["step_index"] = i - 10
                            i -= 10
                            continue

            elif action == 'detect_arr_img':
                target_list = step.get('target_image_arr', [])
                step_num_list = step.get("jump_step_num", [])
                image_arr_index = step.get("image_arr_index", 0)
                max_cycles = 3  # 最多识别轮数
                matched_name = None
                matched_pos = None

                for cycle in range(max_cycles):
                    logger.info(f"[detect_arr_img] 第 {cycle + 1} 轮识别")
                    for idx, target_name in enumerate(target_list):
                        base_name = target_name.split('.')[0]
                        found, pos, offline_status = detect_target(base_name, max_attempts=1, interval=1, vm_index=vm_index)
                        if found:
                            logger.info(f"[detect_arr_img] 识别成功: {base_name} @ {pos}")
                            matched_name = base_name
                            matched_pos = pos
                            break
                    if matched_name:
                        break

                if not matched_name:
                    logger.info("detect_arr_img 全部图像均识别失败")
                    if image_arr_index == 0:
                        logger.info("登录battle失败，开始重复登录battle定时计划")
                        start_relink_battle_timer(quadrant, 0)
                        return True
                    elif image_arr_index == 1 or image_arr_index == 200:
                        logger.info("图像识别失败，判断是掉线状态")
                        config.config.WOW_OFFLINE_STATUS[vm_index] = True
                        config.config.SPECIAL_TASK_ACTIVE[vm_index] = False
                        return True
                    elif image_arr_index == 100:
                        task["step_index"] = i + 1
                        i += 1
                        continue
                    elif image_arr_index == 2:
                        is_in_wow = _is_in_wow_mainpage()
                        if is_in_wow:
                            continue
                        else:
                            logger.info("识别NPC失败，判断是掉线状态")
                            config.config.WOW_OFFLINE_STATUS[vm_index] = True
                            config.config.SPECIAL_TASK_ACTIVE[vm_index] = False
                            return True
                    elif image_arr_index == 300 or image_arr_index == 400:
                        continue
                    elif image_arr_index == 500:
                        task["step_index"] = i - 4
                        i -= 4
                        continue
                        # quit_and_login_wow_task(vm_index)
                        # return True
                    return False
                else:
                    if image_arr_index == 100:
                        if matched_name == 'classic_link_icon':
                            config.config.LINK_ENTER_GAME_INDEX = 11
                        elif matched_name == 'battle_login_btn':
                            config.config.LINK_ENTER_GAME_INDEX = 4
                        config.config.SPECIAL_TASK_RELINK_BATTLE[vm_index] = False
                        relink_battle_task("battle_relink", vm_index)
                        return True

                task["extra"]["last_detect_pos"] = {"x": matched_pos[0], "y": matched_pos[1]}
                task["extra"]["matched_image_name"] = matched_name
                target_index = target_list.index(matched_name + ".png")
                task["extra"]["matched_image_index"] = target_index

                if not serial_operator.USE_HARDWARE_MOUSE or step.get("is_need_click"):
                    if not execute_action(matched_pos[0], matched_pos[1], click_times=1):
                        logger.info(f"识别点击失败: {matched_name}")
                        return False

                step_num = step_num_list[target_index]

                logger.info(f"已识别 {matched_name}，跳过{step_num - 1}步骤")
                i += step_num - 1  # 跳过 input_pwd, detect, click（你需要根据 JSON 确定精确数量）
                task["step_index"] = i + step_num - 1
                continue

            elif action == 'move':
                click_x = step.get("click_x")
                click_y = step.get("click_y")

                # 如果为 -1 或 None，使用上次识别到的坐标
                if (click_x in [None, -1]) or (click_y in [None, -1]):
                    last_pos = task.get("extra", {}).get("last_detect_pos")
                    if not last_pos:
                        raise Exception("点击位置未指定也未从 detect 获取")
                    click_x, click_y = last_pos["x"], last_pos["y"]

                if not execute_action(click_x - 100, click_y - 60, action, click_times=1, click_interval=1):
                    # log_task_execution(task_id, task_type, quadrant, "failed", "点击失败", i)
                    logger.info(f"移动失败")
                    return False

            elif action == 'click':
                click_x = step.get("click_x")
                click_y = step.get("click_y")

                # 如果为 -1 或 None，使用上次识别到的坐标
                if (click_x in [None, -1]) or (click_y in [None, -1]):
                    last_pos = task.get("extra", {}).get("last_detect_pos")
                    if not last_pos:
                        raise Exception("点击位置未指定也未从 detect 获取")
                    click_x, click_y = last_pos["x"], last_pos["y"]

                if not execute_action(click_x, click_y, action, click_times=1, click_interval=1):
                    # log_task_execution(task_id, task_type, quadrant, "failed", "点击失败", i)
                    logger.info(f"点击失败")
                    return False

            elif action == 'double_click':
                click_x = step.get("click_x")
                click_y = step.get("click_y")

                if (click_x in [None, -1]) or (click_y in [None, -1]):
                    last_pos = task.get("extra", {}).get("last_detect_pos")
                    if not last_pos:
                        raise Exception("点击位置未指定也未从 detect 获取")
                    click_x, click_y = last_pos["x"], last_pos["y"]

                if not execute_action(click_x, click_y, action, click_times=1, click_interval=1):
                    logger.info(f"双击失败")
                    return False

            elif action == 'right_click':
                click_x = step.get("click_x")
                click_y = step.get("click_y")

                if (click_x in [None, -1]) or (click_y in [None, -1]):
                    last_pos = task.get("extra", {}).get("last_detect_pos")
                    if not last_pos:
                        raise Exception("点击位置未指定也未从 detect 获取")
                    click_x, click_y = last_pos["x"], last_pos["y"]

                if not execute_action(click_x, click_y, action, click_times=1, click_interval=1):
                    logger.info(f"右击失败")
                    return False

            elif action == 'input_pwd' or action == 'write_current_day' or action == 'write_now_time' or action == 'write_end_status':
                from datetime import datetime
                if action == 'input_pwd':
                    input_text = step.get("content", "")
                elif action == 'write_current_day':
                    input_text = datetime.now().strftime("%Y-%m-%d")
                elif action == 'write_now_time':
                    input_text = datetime.now().strftime("%H-%M-%S")
                elif action == 'write_end_status':
                    input_text = '23-59-59'

                last_pos = task.get("extra", {}).get("last_detect_pos")
                if not last_pos:
                    raise Exception("input_pwd 操作找不到识别位置")

                logger.info(f"[输入密码或当前日期或当前时分秒或结束标志] 点击坐标并输入：{input_text}")
                if not execute_action(last_pos['x'], last_pos['y'], action, content=input_text):
                    logger.info("密码或日期或时分秒或结束状态输入失败")
                    return False

            elif action == 'is_first_sheet':
                if not config.config.IS_RELOGIN_WOW_FLG[vm_index]:
                    if config.config.IS_FIRST_COPY_OPERATE[vm_index]:
                        step_num_list = step.get("jump_step_num", [])
                        step_num = step_num_list[0]
                        task["step_index"] = i + step_num
                        i += step_num
                        config.config.IS_FIRST_COPY_OPERATE[vm_index] = False
                        continue
                    else:
                        step_num_list = step.get("jump_step_num", [])
                        step_num = step_num_list[1]
                        task["step_index"] = i + step_num
                        i += step_num
                        continue
                else:
                    config.config.IS_RELOGIN_WOW_FLG[vm_index] = False

            elif action == 'is_first_excel':
                step_num_list = step.get("jump_step_num", [])
                if config.config.db_current_day_obj[vm_index]:
                    step_num = step_num_list[1]
                    task["step_index"] = i + step_num
                    i += step_num
                    max_index = 23
                    continue
                else:
                    step_num = step_num_list[0]
                    task["step_index"] = i + step_num
                    i += step_num
                    max_index = 17
                    continue

            elif action == 'is_show_excel':
                if config.config.is_show_excel_obj[vm_index]:
                    click_x = step.get("click_x")
                    click_y = step.get("click_y")

                    if not execute_action(click_x, click_y, action='click', click_times=1, click_interval=1):
                        logger.info(f"EXCEL最小化失败")
                        return False

            elif action == 'is_wow_frozen':
                target_name = step['target_image'].split('.')[0]
                found, pos, offline_status = detect_target(target_name, max_attempts=3, interval=2, vm_index=vm_index,
                                                           task_type='is_wow_frozen')
                if found:
                    logger.info("发现WOW卡住现象，复制回退")
                    time.sleep(15)
                    task["step_index"] = 1
                    i = 1
                    continue

            elif action == 'copy_content_click':
                last_pos = task.get("extra", {}).get("last_detect_pos")
                if not last_pos:
                    raise Exception("点击位置未指定也未从 detect 获取")
                click_x, click_y = last_pos["x"], last_pos["y"]

                if not execute_action(click_x - 100, click_y - 60, action='click', click_times=1, click_interval=1):
                    logger.info(f"点击失败")
                    return False

            elif action == 'ctrl_down':
                config.config.is_first_cell_obj[vm_index] = False
                if not execute_action(None, None, action):
                    logger.info("CTRL+DOWN输入失败")
                    return False

            elif action == 'ctrl_c':
                if not execute_action(None, None, action):
                    logger.info("CTRL+C输入失败")
                    return False

            elif action == 'ctrl_a':
                if not execute_action(None, None, action):
                    logger.info("CTRL+A输入失败")
                    return False

            time.sleep(step.get("delay", 0.5))
            task["step_index"] = i + 1
            i += 1

            if not config.config.SPECIAL_TASK_ACTIVE[vm_index] and not config.config.SPECIAL_TASK_RELINK_BATTLE[vm_index]:
                is_step_model = False
                for q in range(config.config.NUM_VMS_TO_START):
                    if (vm_index != q):
                        if config.config.SPECIAL_TASK_ACTIVE[q] or config.config.SPECIAL_TASK_RELINK_BATTLE[q]:
                            is_step_model = True
                            break
                if is_step_model:
                    break

        # log_task_execution(task_id, task_type, quadrant, "done", "执行完成", len(steps))
        logger.info(f"执行完成")
        return True

    except Exception as e:
        # log_task_execution(task_id, task_type, quadrant, "failed", str(e), task.get("step_index", 0))
        logger.info(f"执行报错: {e}")
        return False
