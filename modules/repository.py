from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Protocol


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_DIR = PROJECT_ROOT / "database"
DB_PATH = DATABASE_DIR / "amazon_profit.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    asin TEXT,
    sku TEXT,
    marketplace TEXT,
    purchase_cost REAL NOT NULL DEFAULT 0,
    packaging_cost REAL NOT NULL DEFAULT 0,
    first_leg_cost REAL NOT NULL DEFAULT 0,
    fba_fee REAL NOT NULL DEFAULT 0,
    other_fixed_cost REAL NOT NULL DEFAULT 0,
    commission_rate REAL NOT NULL DEFAULT 0.15,
    storage_rate REAL NOT NULL DEFAULT 0.02,
    return_rate REAL NOT NULL DEFAULT 0.08,
    price REAL NOT NULL DEFAULT 0,
    tacos REAL NOT NULL DEFAULT 0.2,
    daily_sales REAL NOT NULL DEFAULT 0,
    target_margin REAL NOT NULL DEFAULT 0.12,
    stage TEXT NOT NULL DEFAULT '成长期',
    positioning TEXT NOT NULL DEFAULT '增长款',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


SAMPLE_PRODUCTS = [
    {
        "name": "Kitchen Drawer Organizer",
        "asin": "B0DEMO001",
        "sku": "KDO-001-US",
        "marketplace": "US",
        "purchase_cost": 6.2,
        "packaging_cost": 0.45,
        "first_leg_cost": 1.15,
        "fba_fee": 3.05,
        "other_fixed_cost": 0.35,
        "commission_rate": 0.15,
        "storage_rate": 0.02,
        "return_rate": 0.06,
        "price": 24.99,
        "tacos": 0.18,
        "daily_sales": 18,
        "target_margin": 0.12,
        "stage": "成长期",
        "positioning": "增长款",
    },
    {
        "name": "Silicone Travel Bottles",
        "asin": "B0DEMO002",
        "sku": "STB-004-US",
        "marketplace": "US",
        "purchase_cost": 3.3,
        "packaging_cost": 0.28,
        "first_leg_cost": 0.72,
        "fba_fee": 2.78,
        "other_fixed_cost": 0.18,
        "commission_rate": 0.15,
        "storage_rate": 0.015,
        "return_rate": 0.05,
        "price": 16.99,
        "tacos": 0.24,
        "daily_sales": 35,
        "target_margin": 0.10,
        "stage": "成熟期",
        "positioning": "核心款",
    },
    {
        "name": "Pet Grooming Glove",
        "asin": "B0DEMO003",
        "sku": "PGG-002-US",
        "marketplace": "US",
        "purchase_cost": 4.6,
        "packaging_cost": 0.32,
        "first_leg_cost": 0.98,
        "fba_fee": 3.4,
        "other_fixed_cost": 0.25,
        "commission_rate": 0.15,
        "storage_rate": 0.025,
        "return_rate": 0.10,
        "price": 18.99,
        "tacos": 0.31,
        "daily_sales": 12,
        "target_margin": 0.12,
        "stage": "清库存",
        "positioning": "清库存",
    },
]


class ProductRepository(Protocol):
    def init_db(self) -> None:
        ...

    def list_products(self) -> list[dict]:
        ...

    def get_product(self, product_id: int) -> dict | None:
        ...

    def insert_product(self, data: dict) -> int:
        ...

    def update_product(self, product_id: int, data: dict) -> None:
        ...

    def delete_product(self, product_id: int) -> None:
        ...

    def duplicate_product(self, product_id: int) -> int | None:
        ...


class SQLiteProductRepository:
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
            count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            if count == 0:
                for product in SAMPLE_PRODUCTS:
                    self.insert_product(product, conn=conn)

    def list_products(self) -> list[dict]:
        self.init_db()
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
        return [dict(row) for row in rows]

    def get_product(self, product_id: int) -> dict | None:
        self.init_db()
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        return dict(row) if row else None

    def insert_product(self, data: dict, conn: sqlite3.Connection | None = None) -> int:
        keys = [key for key in data.keys() if key != "id"]
        values = [data[key] for key in keys]
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

    def update_product(self, product_id: int, data: dict) -> None:
        keys = [key for key in data.keys() if key != "id"]
        assignments = ", ".join(f"{key} = ?" for key in keys)
        values = [data[key] for key in keys]
        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE products SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values + [product_id],
            )

    def delete_product(self, product_id: int) -> None:
        with self.get_connection() as conn:
            conn.execute("DELETE FROM products WHERE id = ?", (product_id,))

    def duplicate_product(self, product_id: int) -> int | None:
        product = self.get_product(product_id)
        if not product:
            return None
        product.pop("id", None)
        product.pop("created_at", None)
        product.pop("updated_at", None)
        product["name"] = f"{product['name']} - 复制"
        product["sku"] = f"{product.get('sku') or ''}-COPY".strip("-")
        return self.insert_product(product)


repository: ProductRepository = SQLiteProductRepository()
