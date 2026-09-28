"""app/mysql_store.py のテスト。

実際のAzure Database for MySQLには接続できない（このテストは接続情報を持たない）ため、
pymysql.connect が返す接続／カーソルをフェイクに差し替えて、
発行されるSQLと戻り値の組み立てが正しいことを検証する
（実際のAzure MySQLへの疎通確認は、README.mdの手順に沿って
 各自の環境で python -c "from app.database import get_connection; ..." を実行して行うこと）。
"""

from __future__ import annotations

from unittest.mock import patch

from app.records import CartItemRecord
from app import mysql_store


class FakeCursor:
    def __init__(self, fetchone_results=None, fetchall_results=None):
        self.queries: list[tuple[str, tuple]] = []
        self._fetchone_results = list(fetchone_results or [])
        self._fetchall_results = list(fetchall_results or [])
        self.rowcount = 1

    def execute(self, sql, params=()):
        self.queries.append((sql, params))

    def fetchone(self):
        return self._fetchone_results.pop(0) if self._fetchone_results else None

    def fetchall(self):
        return self._fetchall_results.pop(0) if self._fetchall_results else []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeConnection:
    def __init__(self, cursor: FakeCursor):
        self._cursor = cursor
        self.committed = False
        self.closed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def test_get_product_found_builds_record_with_variations():
    cursor = FakeCursor(
        fetchone_results=[
            {
                "product_id": "prod-001",
                "name": "スウェットプルパーカ",
                "category": "トップス",
                "description": "説明",
                "material": "綿100%",
                "care_instructions": "手洗い",
                "country_of_origin": "日本",
                "base_price": 2990,
                "discount_rate": "0.100",  # MySQLのDECIMALはpymysqlだとDecimal/strで返ることがある
                "default_size": "M",
            }
        ],
        fetchall_results=[
            [
                {"sku_id": "sku-001", "product_id": "prod-001", "color": "ブラック", "size": "S", "stock_quantity": 5},
            ]
        ],
    )
    conn = FakeConnection(cursor)

    with patch.object(mysql_store.database, "get_connection", return_value=conn):
        product = mysql_store.get_product("prod-001")

    assert product is not None
    assert product.product_id == "prod-001"
    assert product.discount_rate == 0.1
    assert len(product.variations) == 1
    assert product.variations[0].sku_id == "sku-001"
    assert conn.closed is True


def test_get_product_not_found_returns_none():
    cursor = FakeCursor(fetchone_results=[None])
    conn = FakeConnection(cursor)

    with patch.object(mysql_store.database, "get_connection", return_value=conn):
        product = mysql_store.get_product("does-not-exist")

    assert product is None


def test_upsert_cart_item_uses_on_duplicate_key_update():
    cursor = FakeCursor()
    conn = FakeConnection(cursor)
    item = CartItemRecord(cart_item_id="ci-1", sku_id="sku-001", quantity=3)

    with patch.object(mysql_store.database, "get_connection", return_value=conn):
        mysql_store.upsert_cart_item("cart-1", item)

    sql, params = cursor.queries[0]
    assert "ON DUPLICATE KEY UPDATE" in sql
    assert params == ("ci-1", "cart-1", "sku-001", 3)
    assert conn.committed is True
    assert conn.closed is True


def test_delete_cart_item_returns_true_when_row_deleted():
    cursor = FakeCursor()
    cursor.rowcount = 1
    conn = FakeConnection(cursor)

    with patch.object(mysql_store.database, "get_connection", return_value=conn):
        deleted = mysql_store.delete_cart_item("cart-1", "ci-1")

    assert deleted is True
    assert conn.committed is True


def test_delete_cart_item_returns_false_when_no_row_matched():
    cursor = FakeCursor()
    cursor.rowcount = 0
    conn = FakeConnection(cursor)

    with patch.object(mysql_store.database, "get_connection", return_value=conn):
        deleted = mysql_store.delete_cart_item("cart-1", "does-not-exist")

    assert deleted is False
