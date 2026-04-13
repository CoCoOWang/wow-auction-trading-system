# modules/utils.py
import os
import pymysql

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "123456",
    "database": "wow_auction",
    "charset": "utf8mb4"
}


def get_db_connection():
    return pymysql.connect(**DB_CONFIG)


# === 新增：进度查询/标记 ===
def is_sheet_processed(conn, file_path: str, sheet_name: str) -> bool:
    file_name = os.path.basename(file_path)
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM ingest_progress WHERE file_name=%s AND sheet_name=%s",
                    (file_name, sheet_name))
        return cur.fetchone() is not None


def mark_sheet_done(conn, file_path: str, sheet_name: str, snapshot_time: str, rows_ingested: int):
    file_name = os.path.basename(file_path)
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO ingest_progress (file_name, sheet_name, snapshot_time, rows_ingested, status)
            VALUES (%s,%s,%s,%s,'done')
            ON DUPLICATE KEY UPDATE snapshot_time=VALUES(snapshot_time),
                                    rows_ingested=VALUES(rows_ingested),
                                    status='done'
        """, (file_name, sheet_name, snapshot_time, rows_ingested))
    conn.commit()


# === 新增：为每个 Excel 生成/更新一条 session（可后续手动补 realm/faction/ah_type）===
def ensure_session(conn, file_path: str):
    file_name = os.path.basename(file_path)
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO auction_session (file_name) VALUES (%s)
            ON DUPLICATE KEY UPDATE file_name=file_name
        """, (file_name,))
    conn.commit()


# === 新增：读取税费/押金默认值（优先 session，其次 common_config）===
def load_fee_params(conn, file_path: str):
    file_name = os.path.basename(file_path)
    with conn.cursor() as cur:
        cur.execute("SELECT tax_bps, deposit_copper FROM auction_session WHERE file_name=%s", (file_name,))
        row = cur.fetchone()
        if row and (row[0] is not None or row[1] is not None):
            return (row[0] if row[0] is not None else get_cfg(conn, 'tax_bps'),
                    row[1] if row[1] is not None else get_cfg(conn, 'default_deposit_copper'))
    return (get_cfg(conn, 'tax_bps'), get_cfg(conn, 'default_deposit_copper'))


def get_cfg(conn, key: str) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT cfg_value FROM auction_common_config WHERE cfg_key=%s", (key,))
        row = cur.fetchone()
        return int(row[0]) if row else 0
