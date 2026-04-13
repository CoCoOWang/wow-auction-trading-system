# utils/task_state.py
from __future__ import annotations
from typing import Optional, Dict, Any, List
import pymysql
from datetime import  date
import config.config
from datetime import datetime

# 复用项目里的 DB 配置
from utils.db import DB_CONFIG


def _conn():
    return pymysql.connect(
        host=DB_CONFIG["host"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        charset=DB_CONFIG.get("charset", "utf8mb4"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def _today_str() -> str:
    return date.today().strftime("%Y-%m-%d")


# ---------- 基础写入：插入或更新 ----------
def upsert_status(vm_id: int, task_name: str, status: str,
                  task_date: Optional[str] = None) -> None:
    """
    插入或更新指定 (vm_id, task_name, task_date) 的状态。
    :param status: 'pending' / 'running' / 'paused' / 'failed' / 'success' / 你的自定义
    """
    td = task_date or _today_str()
    sql = """
    INSERT INTO vm_task_state (vm_id, task_name, task_date, status)
    VALUES (%s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
      status = VALUES(status),
      updated_at = CURRENT_TIMESTAMP
    """
    with _conn() as c, c.cursor() as cur:
        cur.execute(sql, (vm_id, task_name, td, status))


def set_status(vm_id: int, task_name: str, status: str,
               task_date: Optional[str] = None) -> None:
    """
    仅更新状态（记录必须已存在；不存在则不创建）。
    """
    td = task_date or _today_str()
    sql = """
    UPDATE vm_task_state
    SET status = %s, updated_at = CURRENT_TIMESTAMP
    WHERE vm_id = %s AND task_name = %s AND task_date = %s
    """
    with _conn() as c, c.cursor() as cur:
        cur.execute(sql, (status, vm_id, task_name, td))


def touch(vm_id: int, task_name: str, task_date: Optional[str] = None) -> None:
    """
    心跳/触达：仅刷新 updated_at（记录存在才生效）。
    """
    td = task_date or _today_str()
    sql = """
    UPDATE vm_task_state
    SET updated_at = CURRENT_TIMESTAMP
    WHERE vm_id = %s AND task_name = %s AND task_date = %s
    """
    with _conn() as c, c.cursor() as cur:
        cur.execute(sql, (vm_id, task_name, td))


# ---------- 查询 ----------
def get_state(vm_id: int, task_name: str,
              task_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """查询单条记录。"""
    td = task_date or _today_str()
    sql = """
    SELECT * FROM vm_task_state
    WHERE vm_id = %s AND task_name = %s AND task_date = %s
    LIMIT 1
    """
    with _conn() as c, c.cursor() as cur:
        cur.execute(sql, (vm_id, task_name, td))
        return cur.fetchone()


def list_vm_tasks(vm_id: int, task_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """查询某 VM 当天所有任务。"""
    td = task_date or _today_str()
    sql = """
    SELECT * FROM vm_task_state
    WHERE vm_id = %s AND task_date = %s
    ORDER BY updated_at DESC
    """
    with _conn() as c, c.cursor() as cur:
        cur.execute(sql, (vm_id, td))
        return cur.fetchall()


def list_task_all_vms(task_name: str, task_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """查询某任务在所有 VM 的当天状态。"""
    td = task_date or _today_str()
    sql = """
    SELECT * FROM vm_task_state
    WHERE task_name = %s AND task_date = %s
    ORDER BY vm_id ASC
    """
    with _conn() as c, c.cursor() as cur:
        cur.execute(sql, (task_name, td))
        return cur.fetchall()


def list_by_status(status: str, task_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """按状态筛当天的所有记录（用于看板/巡检）。"""
    td = task_date or _today_str()
    sql = """
    SELECT * FROM vm_task_state
    WHERE status = %s AND task_date = %s
    ORDER BY updated_at DESC
    """
    with _conn() as c, c.cursor() as cur:
        cur.execute(sql, (status, td))
        return cur.fetchall()


# ---------- 便捷封装 ----------
def start_task(vm_id: int, task_name: str, task_date: Optional[str] = None) -> None:
    """将任务标记为 running（无则创建，有则更新）"""
    upsert_status(vm_id, task_name, status="running", task_date=task_date)


def pause_task(vm_id: int, task_name: str, task_date: Optional[str] = None) -> None:
    set_status(vm_id, task_name, status="paused", task_date=task_date)


def fail_task(vm_id: int, task_name: str, task_date: Optional[str] = None) -> None:
    set_status(vm_id, task_name, status="failed", task_date=task_date)


def complete_task(vm_id: int, task_name: str, task_date: Optional[str] = None) -> None:
    set_status(vm_id, task_name, status="success", task_date=task_date)


def set_current_day():
    config.config.CURRENT_DAY = datetime.now().strftime("%Y-%m-%d")


def set_relogin_wow_state(vm_id: Optional[int] = None,
                          task_name: str = "save_sheet_count",
                          task_date: Optional[str] = None) -> list[bool]:
    """
    查询 vm_task_state 是否存在 sheet_count：
      - 若存在且 >0，则 IS_RELOGIN_WOW_FLG[vm_id-1] = True
      - 否则 False

    :param vm_id: 指定单个 VM；为 None 时处理所有 VM
    :param task_name: 记录 sheet_count 的任务名（默认 'save_sheet_count'）
    :param task_date: 指定日期，默认今天
    :return: IS_RELOGIN_WOW_FLG 列表的当前快照
    """
    td = task_date or _today_str()

    def _eval_one(vid: int) -> bool:
        sc = get_sheet_count(vid, task_name=task_name, task_date=td)
        print(f"查询sheet_count返回的值：{sc}")
        return bool(sc and sc > 0)

    if vm_id is None:
        for vid in range(1, config.config.NUM_VMS_TO_START + 1):
            val = _eval_one(vid - 1)
            config.config.IS_RELOGIN_WOW_FLG[vid - 1] = val
            config.config.IS_FIRST_COPY_OPERATE[vid - 1] = not val
    else:
        val = _eval_one(vm_id - 1)
        config.config.IS_RELOGIN_WOW_FLG[vm_id - 1] = val
        config.config.IS_FIRST_COPY_OPERATE[vm_id - 1] = not val

    return config.config.IS_RELOGIN_WOW_FLG[:]



def select_db_current_day(vm_index: int, task_name: str, task_date: str):
    return get_state(vm_index, task_name, task_date)


def set_sheet_count(vm_id: int, sheet_count: int, task_name: str = "enter_game", task_date: str = None) -> None:
    """写入/更新今天的 sheet 数（有则更）"""
    td = task_date or _today_str()
    sql = """
    INSERT INTO vm_task_state (vm_id, task_name, task_date, status, sheet_count)
    VALUES (%s, %s, %s, 'running', %s)
    ON DUPLICATE KEY UPDATE
      sheet_count = VALUES(sheet_count),
      updated_at = CURRENT_TIMESTAMP
    """
    with _conn() as c, c.cursor() as cur:
        cur.execute(sql, (vm_id, task_name, td, sheet_count))


def get_sheet_count(vm_id: int, task_name: str = "enter_game", task_date: str = None) -> int | None:
    """读取今天的 sheet 数；没有返回 None"""
    td = task_date or _today_str()
    sql = """
    SELECT sheet_count FROM vm_task_state
    WHERE vm_id = %s AND task_name = %s AND task_date = %s
    LIMIT 1
    """
    with _conn() as c, c.cursor() as cur:
        cur.execute(sql, (vm_id, task_name, td))
        row = cur.fetchone()
        return row["sheet_count"] if row and row["sheet_count"] is not None else None


def update_insertting_sheet(vm_id: int, task_name: str,
                            is_insertting_sheet: bool,
                            task_date: Optional[str] = None) -> None:
    """
    新增/修改 is_insertting_sheet：
      - 先尝试 UPDATE
      - 若未命中（rowcount=0），则 INSERT 一条新记录
    """
    td = task_date or datetime.now().strftime("%Y-%m-%d")

    update_sql = """
    UPDATE vm_task_state
    SET is_insertting_sheet = %s, updated_at = CURRENT_TIMESTAMP
    WHERE vm_id = %s AND task_name = %s AND task_date = %s
    """

    insert_sql = """
    INSERT INTO vm_task_state (vm_id, task_name, task_date, status, is_insertting_sheet)
    VALUES (%s, %s, %s, %s, %s)
    """

    with _conn() as c, c.cursor() as cur:
        # 先更新
        cur.execute(update_sql, (is_insertting_sheet, vm_id, task_name, td))
        if cur.rowcount == 0:
            # 没有记录则插入（status 可按需改为 'pending' / 'running'）
            cur.execute(insert_sql, (vm_id, task_name, td, 'running', is_insertting_sheet))


def get_insertting_sheet(vm_id: int, task_name: str,
                         task_date: Optional[str] = None) -> Optional[bool]:
    """
    查询 is_insertting_sheet 字段的值
    """
    td = task_date or datetime.now().strftime("%Y-%m-%d")
    sql = """
    SELECT is_insertting_sheet
    FROM vm_task_state
    WHERE vm_id = %s AND task_name = %s AND task_date = %s
    """
    with _conn() as c, c.cursor() as cur:
        cur.execute(sql, (vm_id, task_name, td))
        row = cur.fetchone()
        return row["is_insertting_sheet"] if row else None


def update_updating_sheet_content(vm_id: int, task_name: str,
                            is_updating_sheet_content: bool,
                            task_date: Optional[str] = None) -> None:
    """
    新增/修改 is_updating_sheet_name：
      - 先尝试 UPDATE
      - 若未命中（rowcount=0），则 INSERT 一条新记录
    """
    td = task_date or datetime.now().strftime("%Y-%m-%d")

    update_sql = """
    UPDATE vm_task_state
    SET is_updating_sheet_content = %s, updated_at = CURRENT_TIMESTAMP
    WHERE vm_id = %s AND task_name = %s AND task_date = %s
    """

    insert_sql = """
    INSERT INTO vm_task_state (vm_id, task_name, task_date, status, is_updating_sheet_content)
    VALUES (%s, %s, %s, %s, %s)
    """

    with _conn() as c, c.cursor() as cur:
        # 先更新
        cur.execute(update_sql, (is_updating_sheet_content, vm_id, task_name, td))
        if cur.rowcount == 0:
            # 没有记录则插入（status 可按需改为 'pending' / 'running'）
            cur.execute(insert_sql, (vm_id, task_name, td, 'running', is_updating_sheet_content))


def get_updating_sheet_content(vm_id: int, task_name: str,
                         task_date: Optional[str] = None) -> Optional[bool]:
    """
    查询 is_updating_sheet_content 字段的值
    """
    td = task_date or datetime.now().strftime("%Y-%m-%d")
    sql = """
    SELECT is_updating_sheet_content
    FROM vm_task_state
    WHERE vm_id = %s AND task_name = %s AND task_date = %s
    """
    with _conn() as c, c.cursor() as cur:
        cur.execute(sql, (vm_id, task_name, td))
        row = cur.fetchone()
        return row["is_updating_sheet_content"] if row else None

