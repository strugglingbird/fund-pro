import os
import sqlite3
from pathlib import Path

import pymysql


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("QUANT_DATA_DIR", BASE_DIR))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "fund_pro.db"
DATABASE_ENGINE = os.environ.get("DATABASE_ENGINE", "sqlite").lower()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    quantity REAL NOT NULL,
    cost_price REAL NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS watchlist_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL CHECK(category IN ('exchange', 'fund')),
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, category)
);
CREATE TABLE IF NOT EXISTS watchlist_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    asset_type TEXT NOT NULL CHECK(asset_type IN ('stock', 'etf', 'fund')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(group_id, code, asset_type),
    FOREIGN KEY(group_id) REFERENCES watchlist_groups(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


MYSQL_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS holdings (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(32) NOT NULL,
    asset_type VARCHAR(16) NOT NULL,
    quantity DOUBLE NOT NULL,
    cost_price DOUBLE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS watchlist_groups (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(16) NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_watchlist_group_name (name, category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS watchlist_items (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    group_id BIGINT NOT NULL,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(32) NOT NULL,
    asset_type VARCHAR(16) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_watchlist_item (group_id, code, asset_type),
    CONSTRAINT fk_watchlist_item_group FOREIGN KEY (group_id) REFERENCES watchlist_groups(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS app_settings (
    `key` VARCHAR(128) PRIMARY KEY,
    value TEXT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


class MySQLConnection:
    """Keep the existing SQLite-like database calls portable to PyMySQL."""

    def __init__(self, connection):
        self.connection = connection

    @staticmethod
    def _adapt_sql(sql):
        return sql.replace("INSERT OR IGNORE", "INSERT IGNORE").replace("?", "%s")

    def execute(self, sql, params=()):
        cursor = self.connection.cursor()
        cursor.execute(self._adapt_sql(sql), params)
        return cursor

    def executemany(self, sql, params):
        cursor = self.connection.cursor()
        cursor.executemany(self._adapt_sql(sql), params)
        return cursor

    def commit(self):
        self.connection.commit()

    def close(self):
        self.connection.close()


def get_connection():
    if DATABASE_ENGINE == "mysql":
        connection = pymysql.connect(
            host=os.environ.get("MYSQL_HOST", "db"),
            port=int(os.environ.get("MYSQL_PORT", "3306")),
            user=os.environ.get("MYSQL_USER", "quant"),
            password=os.environ.get("MYSQL_PASSWORD", ""),
            database=os.environ.get("MYSQL_DATABASE", "quant_workbench"),
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )
        return MySQLConnection(connection)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    try:
        if DATABASE_ENGINE == "mysql":
            for statement in MYSQL_SCHEMA_SQL.split(";"):
                if statement.strip():
                    conn.execute(statement)
            initialized = conn.execute(
                "SELECT value FROM app_settings WHERE `key` = ?",
                ("watchlist_defaults_initialized",)
            ).fetchone()
            if not initialized:
                conn.executemany(
                    "INSERT IGNORE INTO watchlist_groups (name, category) VALUES (?, ?)",
                    [("场内自选", "exchange"), ("场外基金", "fund")]
                )
                conn.execute(
                    "INSERT INTO app_settings (`key`, value) VALUES (?, ?) ON DUPLICATE KEY UPDATE value = VALUES(value)",
                    ("watchlist_defaults_initialized", "1")
                )
            conn.execute("DROP TABLE IF EXISTS sector_fund_flow_snapshots")
            conn.commit()
            return
        conn.executescript(SCHEMA_SQL)
        conn.execute("DROP TABLE IF EXISTS sector_fund_flow_snapshots")
        group_columns = {row["name"] for row in conn.execute("PRAGMA table_info(watchlist_groups)").fetchall()}
        if "sort_order" not in group_columns:
            conn.execute("ALTER TABLE watchlist_groups ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0")
        conn.execute("UPDATE watchlist_groups SET sort_order = id WHERE sort_order = 0")
        initialized = conn.execute(
            "SELECT value FROM app_settings WHERE key = 'watchlist_defaults_initialized'"
        ).fetchone()
        if not initialized:
            conn.executemany(
                "INSERT OR IGNORE INTO watchlist_groups (name, category) VALUES (?, ?)",
                [("场内自选", "exchange"), ("场外基金", "fund")]
            )
            conn.execute(
                "INSERT INTO app_settings (key, value) VALUES ('watchlist_defaults_initialized', '1')"
            )
        conn.commit()
    finally:
        conn.close()
