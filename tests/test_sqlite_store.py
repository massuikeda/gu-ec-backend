"""app/sqlite_store.py のテスト。

MySQL版（test_mysql_store.py）と違い、SQLiteはファイル1つで動くので、
pytestの一時ディレクトリ（tmp_path）に本物のDBを作って実際にSQLを実行して確認する。
後半ではAPI（TestClient）もSQLiteモードで通しで動かし、
再起動相当（新しい接続）でもカートが残る＝永続化されていることを確認する。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import database, sqlite_store
from app.main import app
from app.records import CartItemRecord


@pytest.fixture
def sqlite_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("SQLITE_PATH", str(db_file))
    with patch.object(database, "DB_BACKEND", "sqlite"):
        sqlite_store.init_db()
        yield db_file


def test_init_db_is_idempotent(sqlite_db):
    # 1回目はfixtureで実行済みなので、2回目は何も追加されない。
    assert sqlite_store.init_db() == (0, 0)


def test_get_product_returns_seeded_data(sqlite_db):
    product = sqlite_store.get_product("prod-001")
    assert product is not None
    assert product.name == "スウェットプルパーカ"
    assert product.base_price == 2990
    assert product.discount_rate == 0.0
    assert [v.sku_id for v in product.variations] == [f"sku-00{i}" for i in range(1, 7)]


def test_get_product_not_found(sqlite_db):
    assert sqlite_store.get_product("does-not-exist") is None


def test_find_variation_by_sku(sqlite_db):
    v = sqlite_store.find_variation_by_sku("sku-003")
    assert v is not None
    assert (v.color, v.size, v.stock_quantity) == ("ブラック", "L", 120)
    assert sqlite_store.find_variation_by_sku("nope") is None


def test_cart_upsert_insert_then_update_and_delete(sqlite_db):
    sqlite_store.upsert_cart_item("cart-1", CartItemRecord("ci-1", "sku-001", 2))
    assert sqlite_store.get_cart_item("cart-1", "ci-1").quantity == 2

    sqlite_store.upsert_cart_item("cart-1", CartItemRecord("ci-1", "sku-001", 4))
    items = sqlite_store.get_cart_items("cart-1")
    assert len(items) == 1 and items[0].quantity == 4
    assert sqlite_store.find_cart_item_by_sku("cart-1", "sku-001").cart_item_id == "ci-1"

    # 別のカートからは見えない
    assert sqlite_store.get_cart_items("cart-2") == []
    assert sqlite_store.delete_cart_item("cart-2", "ci-1") is False

    assert sqlite_store.delete_cart_item("cart-1", "ci-1") is True
    assert sqlite_store.get_cart_items("cart-1") == []


def test_foreign_key_rejects_unknown_sku(sqlite_db):
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        sqlite_store.upsert_cart_item("cart-1", CartItemRecord("ci-x", "sku-unknown", 1))


def test_api_end_to_end_on_sqlite(sqlite_db):
    # with を使うと起動時処理（lifespan＝init_db）も走る。
    with TestClient(app) as client:
        res = client.get("/api/products/prod-001")
        assert res.status_code == 200
        assert res.json()["name"] == "スウェットプルパーカ"

        res = client.post("/api/cart/items", json={"skuId": "sku-001", "quantity": 2})
        assert res.status_code == 201
        cart_id = res.cookies.get("cart_id")

    # 新しいクライアント（サーバー再起動相当）でも、同じcart_idならカートが残っている。
    with TestClient(app) as client:
        client.cookies.set("cart_id", cart_id)
        body = client.get("/api/cart").json()
        assert body["cartTotalQuantity"] == 2
        assert body["cartTotalPrice"] == 2990 * 2


def test_api_quantity_changes_are_saved_on_sqlite(sqlite_db):
    """同じSKUの追加・数量変更が、DBモードでも保存され、在庫上限を超えられないこと。"""
    with TestClient(app) as client:
        # sku-001: ブラックS、在庫5
        res = client.post("/api/cart/items", json={"skuId": "sku-001", "quantity": 3})
        assert res.status_code == 201
        item_id = res.json()["cartItemId"]

        res = client.post("/api/cart/items", json={"skuId": "sku-001", "quantity": 2})
        assert res.status_code == 201
        assert res.json()["cartItemId"] == item_id
        assert res.json()["quantity"] == 5

        # 既に5個入っているので、もう1個は上限超過
        res = client.post("/api/cart/items", json={"skuId": "sku-001", "quantity": 1})
        assert res.status_code == 422
        assert res.json()["errorCode"] == "QUANTITY_EXCEEDS_LIMIT"
        assert client.get("/api/cart").json()["cartTotalQuantity"] == 5

        res = client.patch(f"/api/cart/items/{item_id}", json={"quantity": 2})
        assert res.status_code == 200
        assert client.get("/api/cart").json()["cartTotalQuantity"] == 2

        res = client.patch(f"/api/cart/items/{item_id}", json={"quantity": 6})
        assert res.status_code == 422
        assert client.get("/api/cart").json()["cartTotalQuantity"] == 2
