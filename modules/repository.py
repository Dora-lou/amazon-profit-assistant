from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Protocol


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_DIR = PROJECT_ROOT / "database"
DB_PATH = DATABASE_DIR / "amazon_profit.db"


PRODUCT_FIELDS = [
    "asin",
    "fnsku",
    "name",
    "purchase_packaging_cny",
    "first_leg_cny",
    "fba_fee",
    "commission_rate",
    "exchange_rate",
    "price",
    "average_sale_price",
    "daily_sales",
    "tacos",
    "target_tacos",
    "target_margin",
    "return_rate",
    "storage_rate",
    "stage",
    "positioning",
]

DAILY_RECORD_FIELDS = [
    "product_id",
    "record_date",
    "average_sale_price",
    "sessions",
    "units",
    "ad_spend",
    "tacos",
    "note",
]


SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asin TEXT NOT NULL,
    fnsku TEXT,
    name TEXT NOT NULL,
    purchase_packaging_cny REAL NOT NULL DEFAULT 0,
    first_leg_cny REAL NOT NULL DEFAULT 0,
    fba_fee REAL NOT NULL DEFAULT 0,
    commission_rate REAL NOT NULL DEFAULT 0.15,
    exchange_rate REAL NOT NULL DEFAULT 7.2,
    price REAL NOT NULL DEFAULT 0,
    average_sale_price REAL NOT NULL DEFAULT 0,
    daily_sales REAL NOT NULL DEFAULT 0,
    tacos REAL NOT NULL DEFAULT 0.2,
    target_tacos REAL NOT NULL DEFAULT 0.2,
    target_margin REAL NOT NULL DEFAULT 0.12,
    return_rate REAL NOT NULL DEFAULT 0.08,
    storage_rate REAL NOT NULL DEFAULT 0.02,
    stage TEXT NOT NULL DEFAULT '成长期',
    positioning TEXT NOT NULL DEFAULT '增长款',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT NOT NULL,
    record_date TEXT NOT NULL,
    average_sale_price REAL NOT NULL DEFAULT 0,
    sessions REAL NOT NULL DEFAULT 0,
    units REAL NOT NULL DEFAULT 0,
    ad_spend REAL NOT NULL DEFAULT 0,
    tacos REAL NOT NULL DEFAULT 0,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(product_id, record_date)
);
"""


SAMPLE_PRODUCTS = [
    {
        "asin": "B0DEMO001",
        "fnsku": "X003KDO001",
        "name": "Kitchen Drawer Organizer",
        "purchase_packaging_cny": 47.88,
        "first_leg_cny": 8.28,
        "fba_fee": 3.05,
        "commission_rate": 0.15,
        "exchange_rate": 7.2,
        "price": 24.99,
        "average_sale_price": 24.99,
        "daily_sales": 18,
        "tacos": 0.18,
        "target_tacos": 0.20,
        "target_margin": 0.12,
        "return_rate": 0.06,
        "storage_rate": 0.02,
        "stage": "成长期",
        "positioning": "增长款",
    },
    {
        "asin": "B0DEMO002",
        "fnsku": "X003STB004",
        "name": "Silicone Travel Bottles",
        "purchase_packaging_cny": 25.78,
        "first_leg_cny": 5.18,
        "fba_fee": 2.78,
        "commission_rate": 0.15,
        "exchange_rate": 7.2,
        "price": 16.99,
        "average_sale_price": 16.99,
        "daily_sales": 35,
        "tacos": 0.24,
        "target_tacos": 0.20,
        "target_margin": 0.10,
        "return_rate": 0.05,
        "storage_rate": 0.015,
        "stage": "成熟期",
        "positioning": "核心款",
    },
    {
        "asin": "B0DEMO003",
        "fnsku": "X003PGG002",
        "name": "Pet Grooming Glove",
        "purchase_packaging_cny": 35.42,
        "first_leg_cny": 7.06,
        "fba_fee": 3.40,
        "commission_rate": 0.15,
        "exchange_rate": 7.2,
        "price": 18.99,
        "average_sale_price": 18.99,
        "daily_sales": 12,
        "tacos": 0.31,
        "target_tacos": 0.20,
        "target_margin": 0.12,
        "return_rate": 0.10,
        "storage_rate": 0.025,
        "stage": "清库存",
        "positioning": "清库存",
    },
]


class ProductRepository(Protocol):
    backend_name: str
    is_cloud_persistent: bool

    def init_db(self) -> None:
        ...

    def list_products(self) -> list[dict]:
        ...

    def get_product(self, product_id: int) -> dict | None:
        ...

    def insert_product(self, data: dict) -> int | str:
        ...

    def update_product(self, product_id: int | str, data: dict) -> None:
        ...

    def delete_product(self, product_id: int | str) -> None:
        ...

    def duplicate_product(self, product_id: int | str) -> int | str | None:
        ...

    def list_daily_records(self, product_id: int | str) -> list[dict]:
        ...

    def upsert_daily_record(self, data: dict) -> int | str:
        ...

    def update_daily_record(self, record_id: int | str, data: dict) -> None:
        ...

    def delete_daily_record(self, record_id: int | str) -> None:
        ...


def clean_product_data(data: dict) -> dict:
    return {key: data.get(key) for key in PRODUCT_FIELDS}


def normalize_row(row: dict) -> dict:
    normalized = dict(row)
    normalized.setdefault("fnsku", normalized.get("sku", ""))
    normalized.setdefault("purchase_packaging_cny", 0)
    normalized.setdefault("first_leg_cny", 0)
    normalized.setdefault("exchange_rate", 7.2)
    normalized.setdefault("average_sale_price", normalized.get("price", 0))
    normalized.setdefault("target_tacos", 0.2)
    for key in PRODUCT_FIELDS:
        normalized.setdefault(key, "" if key in {"asin", "fnsku", "name", "stage", "positioning"} else 0)
    return normalized


def clean_daily_record_data(data: dict) -> dict:
    return {key: data.get(key) for key in DAILY_RECORD_FIELDS}


def normalize_daily_record(row: dict) -> dict:
    normalized = dict(row)
    normalized.setdefault("note", "")
    for key in DAILY_RECORD_FIELDS:
        normalized.setdefault(key, "" if key in {"product_id", "record_date", "note"} else 0)
    return normalized


class SQLiteProductRepository:
    backend_name = "SQLite"
    is_cloud_persistent = False

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        DATABASE_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self.get_connection() as conn:
            conn.executescript(SCHEMA)
            self._migrate_legacy_columns(conn)
            count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            if count == 0:
                for product in SAMPLE_PRODUCTS:
                    self.insert_product(product, conn=conn)

    def _migrate_legacy_columns(self, conn: sqlite3.Connection) -> None:
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(products)").fetchall()}
        additions = {
            "fnsku": "TEXT",
            "purchase_packaging_cny": "REAL NOT NULL DEFAULT 0",
            "first_leg_cny": "REAL NOT NULL DEFAULT 0",
            "exchange_rate": "REAL NOT NULL DEFAULT 7.2",
            "average_sale_price": "REAL NOT NULL DEFAULT 0",
            "target_tacos": "REAL NOT NULL DEFAULT 0.2",
        }
        for column, definition in additions.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE products ADD COLUMN {column} {definition}")

        legacy = {row["name"] for row in conn.execute("PRAGMA table_info(products)").fetchall()}
        if {"purchase_cost", "packaging_cost", "first_leg_cost", "sku"}.issubset(legacy):
            conn.execute(
                """
                UPDATE products
                SET
                    fnsku = COALESCE(NULLIF(fnsku, ''), sku, ''),
                    purchase_packaging_cny = CASE
                        WHEN purchase_packaging_cny = 0 THEN (COALESCE(purchase_cost, 0) + COALESCE(packaging_cost, 0)) * exchange_rate
                        ELSE purchase_packaging_cny
                    END,
                    first_leg_cny = CASE
                        WHEN first_leg_cny = 0 THEN COALESCE(first_leg_cost, 0) * exchange_rate
                        ELSE first_leg_cny
                    END,
                    average_sale_price = CASE
                        WHEN average_sale_price = 0 THEN price
                        ELSE average_sale_price
                    END
                """
            )

    def list_products(self) -> list[dict]:
        self.init_db()
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM products ORDER BY updated_at DESC, id DESC").fetchall()
        return [normalize_row(dict(row)) for row in rows]

    def get_product(self, product_id: int | str) -> dict | None:
        self.init_db()
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        return normalize_row(dict(row)) if row else None

    def insert_product(self, data: dict, conn: sqlite3.Connection | None = None) -> int:
        payload = clean_product_data(data)
        keys = list(payload.keys())
        values = [payload[key] for key in keys]
        sql = f"INSERT INTO products ({', '.join(keys)}) VALUES ({', '.join(['?'] * len(keys))})"
        own_conn = conn is None
        if own_conn:
            conn = self.get_connection()
        assert conn is not None
        cur = conn.execute(sql, values)
        if own_conn:
            conn.commit()
            conn.close()
        return int(cur.lastrowid)

    def update_product(self, product_id: int | str, data: dict) -> None:
        payload = clean_product_data(data)
        assignments = ", ".join(f"{key} = ?" for key in payload.keys())
        values = [payload[key] for key in payload.keys()]
        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE products SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values + [product_id],
            )

    def delete_product(self, product_id: int | str) -> None:
        with self.get_connection() as conn:
            conn.execute("DELETE FROM daily_records WHERE product_id = ?", (str(product_id),))
            conn.execute("DELETE FROM products WHERE id = ?", (product_id,))

    def duplicate_product(self, product_id: int | str) -> int | None:
        product = self.get_product(product_id)
        if not product:
            return None
        product = clean_product_data(product)
        product["asin"] = f"{product.get('asin') or ''}-COPY".strip("-")
        product["fnsku"] = f"{product.get('fnsku') or ''}-COPY".strip("-")
        product["name"] = f"{product['name']} - 复制"
        return self.insert_product(product)

    def list_daily_records(self, product_id: int | str) -> list[dict]:
        self.init_db()
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM daily_records WHERE product_id = ? ORDER BY record_date DESC, id DESC",
                (str(product_id),),
            ).fetchall()
        return [normalize_daily_record(dict(row)) for row in rows]

    def upsert_daily_record(self, data: dict) -> int:
        payload = clean_daily_record_data(data)
        keys = list(payload.keys())
        values = [payload[key] for key in keys]
        placeholders = ", ".join(["?"] * len(keys))
        updates = ", ".join(f"{key} = excluded.{key}" for key in keys if key not in {"product_id", "record_date"})
        with self.get_connection() as conn:
            cur = conn.execute(
                f"""
                INSERT INTO daily_records ({', '.join(keys)})
                VALUES ({placeholders})
                ON CONFLICT(product_id, record_date) DO UPDATE SET
                    {updates},
                    updated_at = CURRENT_TIMESTAMP
                """,
                values,
            )
            record = conn.execute(
                "SELECT id FROM daily_records WHERE product_id = ? AND record_date = ?",
                (payload["product_id"], payload["record_date"]),
            ).fetchone()
        return int(record["id"] if record else cur.lastrowid)

    def update_daily_record(self, record_id: int | str, data: dict) -> None:
        payload = clean_daily_record_data(data)
        assignments = ", ".join(f"{key} = ?" for key in payload.keys())
        values = [payload[key] for key in payload.keys()]
        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE daily_records SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values + [record_id],
            )

    def delete_daily_record(self, record_id: int | str) -> None:
        with self.get_connection() as conn:
            conn.execute("DELETE FROM daily_records WHERE id = ?", (record_id,))


class SupabaseProductRepository:
    backend_name = "Supabase"
    is_cloud_persistent = True

    def __init__(self, url: str, key: str) -> None:
        from supabase import create_client

        self.client = create_client(url, key)
        self.table = self.client.table("products")

    def init_db(self) -> None:
        result = self.table.select("id").limit(1).execute()
        if not result.data:
            for product in SAMPLE_PRODUCTS:
                self.insert_product(product)

    def list_products(self) -> list[dict]:
        self.init_db()
        result = self.table.select("*").order("updated_at", desc=True).execute()
        return [normalize_row(row) for row in result.data]

    def get_product(self, product_id: int | str) -> dict | None:
        result = self.table.select("*").eq("id", product_id).limit(1).execute()
        return normalize_row(result.data[0]) if result.data else None

    def insert_product(self, data: dict) -> str:
        result = self.table.insert(clean_product_data(data)).execute()
        return result.data[0]["id"]

    def update_product(self, product_id: int | str, data: dict) -> None:
        self.table.update(clean_product_data(data)).eq("id", product_id).execute()

    def delete_product(self, product_id: int | str) -> None:
        self.client.table("daily_records").delete().eq("product_id", str(product_id)).execute()
        self.table.delete().eq("id", product_id).execute()

    def duplicate_product(self, product_id: int | str) -> str | None:
        product = self.get_product(product_id)
        if not product:
            return None
        product = clean_product_data(product)
        product["asin"] = f"{product.get('asin') or ''}-COPY".strip("-")
        product["fnsku"] = f"{product.get('fnsku') or ''}-COPY".strip("-")
        product["name"] = f"{product['name']} - 复制"
        return self.insert_product(product)

    def list_daily_records(self, product_id: int | str) -> list[dict]:
        result = (
            self.client.table("daily_records")
            .select("*")
            .eq("product_id", str(product_id))
            .order("record_date", desc=True)
            .execute()
        )
        return [normalize_daily_record(row) for row in result.data]

    def upsert_daily_record(self, data: dict) -> str:
        payload = clean_daily_record_data(data)
        result = (
            self.client.table("daily_records")
            .upsert(payload, on_conflict="product_id,record_date")
            .execute()
        )
        return result.data[0]["id"]

    def update_daily_record(self, record_id: int | str, data: dict) -> None:
        self.client.table("daily_records").update(clean_daily_record_data(data)).eq("id", record_id).execute()

    def delete_daily_record(self, record_id: int | str) -> None:
        self.client.table("daily_records").delete().eq("id", record_id).execute()


def _secret_value(name: str) -> str | None:
    try:
        import streamlit as st

        value = st.secrets.get(name)
        if value:
            return str(value)
    except Exception:
        pass
    return os.getenv(name)


def get_repository() -> ProductRepository:
    url = _secret_value("SUPABASE_URL")
    key = _secret_value("SUPABASE_ANON_KEY")
    if url and key:
        return SupabaseProductRepository(url, key)
    return SQLiteProductRepository()


repository: ProductRepository = get_repository()
