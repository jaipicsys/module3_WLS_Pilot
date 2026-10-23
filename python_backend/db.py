import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DB = os.path.join(BASE_DIR, "data.db")
# The saved run used by recorded mode (read-only). Change the name here, or set
# the RECORDED_DB_FILE environment variable. It must sit next to data.db.
RECORDED_DB_FILE = os.environ.get("RECORDED_DB_FILE", "oct_23_11_34.db")
RECORDED_DB = os.path.join(BASE_DIR, RECORDED_DB_FILE)
AUTH_DB = os.path.join(BASE_DIR, "auth.db")

DEFAULT_PLANT = "Unit 1 Textile"


# ---------------- DATABASE CONNECTIONS ----------------

MODES = ("live", "recorded")


def recorded_available():
    return os.path.exists(RECORDED_DB)


def get_db_connection(mode="live"):
    """
    Connection to the production tables.
      mode="live"     -> data.db (what the cameras are writing now)
      mode="recorded" -> recorded.db, opened read-only (a saved run)
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")

    if mode == "recorded":
        if not recorded_available():
            raise FileNotFoundError(f"{RECORDED_DB_FILE} not found")
        conn = sqlite3.connect(RECORDED_DB, timeout=30)
        conn.execute("PRAGMA query_only = ON")  # recorded data can never change
    else:
        conn = sqlite3.connect(DATA_DB, timeout=30)

    conn.row_factory = sqlite3.Row
    return conn


def get_auth_db_connection():
    """Connection to auth.db (users)."""
    conn = sqlite3.connect(AUTH_DB, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------- COMMON MIGRATION HELPER ----------------

def add_missing_columns(conn, table_name, columns):
    """Add columns that do not exist yet. Existing rows are preserved."""
    existing = {
        row["name"]
        for row in conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    }

    for column_name, definition in columns.items():
        if column_name not in existing:
            conn.execute(
                f'ALTER TABLE "{table_name}" '
                f'ADD COLUMN "{column_name}" {definition}'
            )
            print(f"[DB] Added {column_name} to {table_name}")


# ---------------- AUTH DATABASE (auth.db) ----------------

def init_auth_db():
    conn = get_auth_db_connection()

    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role INTEGER DEFAULT 0,
                plant TEXT DEFAULT 'Unit 1 Textile'
            )
        """)

        add_missing_columns(conn, "users", {
            "plant": "TEXT DEFAULT 'Unit 1 Textile'"
        })

        conn.commit()
        print("[DB] Auth tables initialized.")

    finally:
        conn.close()


# ---------------- OPERATOR STATUS ----------------

def init_operator_status_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS operator_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            line_id TEXT,
            product_name TEXT,
            shift_id TEXT,
            shift_timings TEXT,
            break_name TEXT,
            break_timings TEXT,
            operation TEXT,
            station_name TEXT,
            cam_id INTEGER,
            start_time TEXT NOT NULL,
            end_time TEXT,
            durations REAL,
            operator_id TEXT,
            status TEXT,
            reasons TEXT,
            plant TEXT DEFAULT 'Unit 1 Textile'
        )
    """)

    add_missing_columns(conn, "operator_status", {
        "plant": "TEXT DEFAULT 'Unit 1 Textile'"
    })

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_operator_status_station_time
        ON operator_status (station_name, start_time)
    """)


# ---------------- UNIT COUNT ----------------

def init_unit_count_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS unit_count (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            line_id TEXT,
            product_name TEXT,
            shift_id TEXT,
            shift_timings TEXT,
            break_name TEXT,
            break_timings TEXT,
            operation TEXT,
            station_name TEXT,
            cam_id INTEGER,
            unit_count INTEGER,
            plant TEXT DEFAULT 'Unit 1 Textile',
            count_date TEXT,
            updated_at TEXT
        )
    """)

    add_missing_columns(conn, "unit_count", {
        "plant": "TEXT DEFAULT 'Unit 1 Textile'",
        "count_date": "TEXT",
        "updated_at": "TEXT",
    })


# ---------------- CYCLE TIME ----------------

def init_cycle_time_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cycle_time (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            line_id TEXT,
            product_name TEXT,
            shift_id TEXT,
            shift_timings TEXT,
            break_name TEXT,
            break_timings TEXT,
            operation TEXT,
            station_name TEXT,
            cam_id INTEGER,
            step TEXT,
            cycle_id TEXT,
            start_time TEXT,
            end_time TEXT,
            plant TEXT DEFAULT 'Unit 1 Textile'
        )
    """)

    add_missing_columns(conn, "cycle_time", {
        "plant": "TEXT DEFAULT 'Unit 1 Textile'"
    })


# ---------------- DATA DATABASE (data.db) ----------------

def init_data_db():
    conn = get_db_connection()

    try:
        # WAL lets camera threads write while the API reads.
        conn.execute("PRAGMA journal_mode=WAL")

        init_operator_status_table(conn)
        init_unit_count_table(conn)
        init_cycle_time_table(conn)

        conn.commit()
        print("[DB] Production tables initialized.")

    finally:
        conn.close()


# ---------------- INITIALIZE ALL ----------------

def init_all_databases():
    init_auth_db()
    init_data_db()
    print("[DB] All databases initialized successfully.")