# utils/offset_cache.py
from typing import Optional, Tuple, Dict
import threading
import pymysql

# 项目里的 DB_CONFIG 已经有了，这里直接引用
from utils.db import DB_CONFIG

# 全局只读缓存（启动时加载）
# 结构： {(image_key, vm_tag, screen_w, screen_h): (offset_x, offset_y)}
_OFFSETS: Dict[tuple, tuple] = {}
_LOCK = threading.RLock()


def _conn():
    # 项目里如果已有 get_conn() 可直接用，这里给一个本地实现
    return pymysql.connect(
        host=DB_CONFIG["host"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        charset=DB_CONFIG.get("charset","utf8mb4"),
        cursorclass=pymysql.cursors.DictCursor,  # 返回字典而不是元组
        autocommit=True
    )


def _key(image_key: str, vm_tag: Optional[str], screen_w: Optional[int], screen_h: Optional[int]) -> tuple:
    return (image_key, vm_tag or "", screen_w or 0, screen_h or 0)


def load_offsets_into_memory(vm_tag: Optional[str]=None, screen_w: Optional[int]=None, screen_h: Optional[int]=None) -> None:
    """
    系统初始化（开启虚拟机之前）调用。
    如果传了 vm_tag/screen，会优先加载匹配的；不传则全表加载（一般启动一次全加载更简单）。
    """
    global _OFFSETS
    with _LOCK, _conn() as conn, conn.cursor() as cur:
        if vm_tag or (screen_w and screen_h):
            sql = """
            SELECT image_key, vm_tag, screen_w, screen_h, offset_x, offset_y
            FROM image_offset_cache
            WHERE (%s IS NULL OR vm_tag = %s)
              AND (%s IS NULL OR %s IS NULL OR (screen_w = %s AND screen_h = %s))
            """
            cur.execute(sql, (vm_tag, vm_tag, screen_w, screen_h, screen_w, screen_h))
        else:
            sql = "SELECT image_key, vm_tag, screen_w, screen_h, offset_x, offset_y FROM image_offset_cache"
            cur.execute(sql)

        rows = cur.fetchall()
        temp = {}
        for r in rows:
            k = _key(r["image_key"], r["vm_tag"], r["screen_w"], r["screen_h"])
            temp[k] = (r["offset_x"], r["offset_y"])
        print(f"所有的偏移量展示：{temp}")
        _OFFSETS = temp  # 原子替换


def get_offset(image_key: str, vm_tag: Optional[str], screen_w: Optional[int], screen_h: Optional[int]) -> Optional[Tuple[int,int]]:
    """
    供识别前查询。如果命中缓存，直接返回 (x, y)，上层就可跳过识别。
    """
    k_exact = _key(image_key, vm_tag, screen_w, screen_h)
    print(f"偏移量key值：{k_exact}")
    with _LOCK:
        print(f"是否是完全匹配：{k_exact in _OFFSETS}")
        # 先查完全匹配
        if k_exact in _OFFSETS:
            return _OFFSETS[k_exact]
        # 再退化匹配（如果希望允许不带上下文）
        k_loose = _key(image_key, None, None, None)
        return _OFFSETS.get(k_loose, None)


def upsert_offset(image_key: str, offset_x: int, offset_y: int,
                  vm_tag: Optional[str], screen_w: Optional[int], screen_h: Optional[int],
                  confidence: Optional[float]=None, source: str="auto") -> None:
    """
    首次识别成功后，把偏移写库 & 同步内存。
    """
    with _LOCK, _conn() as conn, conn.cursor() as cur:
        sql = """
        INSERT INTO image_offset_cache (image_key, vm_tag, screen_w, screen_h, offset_x, offset_y, confidence, source)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
          offset_x = VALUES(offset_x),
          offset_y = VALUES(offset_y),
          confidence = VALUES(confidence),
          source = VALUES(source),
          updated_at = CURRENT_TIMESTAMP
        """
        cur.execute(sql, (image_key, vm_tag, screen_w, screen_h, offset_x, offset_y, confidence, source))
        # 同步内存
        k = _key(image_key, vm_tag, screen_w, screen_h)
        _OFFSETS[k] = (offset_x, offset_y)
