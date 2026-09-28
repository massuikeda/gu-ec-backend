"""カートAPI（app/routers/cart.py）のテスト。

在庫数・運用上限99のバリデーション（設計書「入力値・数量の制約定義とエラー処理設計」）を
中心に確認する。data.CART_STORE はプロセス内グローバルなインメモリ状態のため、
各テストの前にクリアして、テスト間の状態の持ち越しを防いでいる。
"""

import pytest
from fastapi.testclient import TestClient

from app import data
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_cart_store():
    data.CART_STORE.clear()
    yield
    data.CART_STORE.clear()


def test_add_item_creates_cart_and_sets_cookie():
    # sku-001: ブラックS、在庫5、単価2990円（discountRate=0のため）
    res = client.post("/api/cart/items", json={"skuId": "sku-001", "quantity": 2})
    assert res.status_code == 201
    body = res.json()
    assert body["quantity"] == 2
    assert body["subtotal"] == 2990 * 2
    assert body["cartTotalQuantity"] == 2
    assert res.cookies.get("cart_id") is not None


def test_add_item_out_of_stock():
    # sku-002: ブラックM、在庫0
    res = client.post("/api/cart/items", json={"skuId": "sku-002", "quantity": 1})
    assert res.status_code == 409
    assert res.json()["errorCode"] == "OUT_OF_STOCK"


def test_add_item_sku_not_found():
    res = client.post("/api/cart/items", json={"skuId": "sku-999", "quantity": 1})
    assert res.status_code == 404
    assert res.json()["errorCode"] == "SKU_NOT_FOUND"


def test_add_item_quantity_exceeds_stock():
    # sku-001: 在庫5。6個は上限超え。
    res = client.post("/api/cart/items", json={"skuId": "sku-001", "quantity": 6})
    assert res.status_code == 422
    assert res.json()["errorCode"] == "QUANTITY_EXCEEDS_LIMIT"


def test_add_item_quantity_exceeds_operational_max():
    # sku-003: 在庫120だが運用上限99を優先する。
    res = client.post("/api/cart/items", json={"skuId": "sku-003", "quantity": 100})
    assert res.status_code == 422
    assert res.json()["errorCode"] == "QUANTITY_EXCEEDS_LIMIT"


def test_add_item_twice_merges_quantity():
    res1 = client.post("/api/cart/items", json={"skuId": "sku-001", "quantity": 2})
    cart_id = res1.cookies.get("cart_id")
    client.cookies.set("cart_id", cart_id)

    res2 = client.post("/api/cart/items", json={"skuId": "sku-001", "quantity": 2})
    assert res2.status_code == 201
    assert res2.json()["quantity"] == 4  # 2 + 2 に統合される

    client.cookies.clear()


def test_add_item_merge_exceeding_limit_is_rejected():
    res1 = client.post("/api/cart/items", json={"skuId": "sku-001", "quantity": 4})
    cart_id = res1.cookies.get("cart_id")
    client.cookies.set("cart_id", cart_id)

    # 既に4個入っている状態で+2個 -> 合計6個は在庫5を超えるため拒否される。
    res2 = client.post("/api/cart/items", json={"skuId": "sku-001", "quantity": 2})
    assert res2.status_code == 422
    assert res2.json()["errorCode"] == "QUANTITY_EXCEEDS_LIMIT"
    # 拒否されているので、既存の数量4は変化していないこと。
    get_res = client.get("/api/cart")
    assert get_res.json()["cartTotalQuantity"] == 4

    client.cookies.clear()


def test_get_cart_without_cookie_returns_empty():
    res = client.get("/api/cart")
    assert res.status_code == 200
    body = res.json()
    assert body["cartId"] is None
    assert body["items"] == []
    assert body["cartTotalQuantity"] == 0


def test_update_and_delete_cart_item():
    add_res = client.post("/api/cart/items", json={"skuId": "sku-001", "quantity": 1})
    cart_id = add_res.cookies.get("cart_id")
    cart_item_id = add_res.json()["cartItemId"]
    client.cookies.set("cart_id", cart_id)

    patch_res = client.patch(f"/api/cart/items/{cart_item_id}", json={"quantity": 3})
    assert patch_res.status_code == 200
    assert patch_res.json()["quantity"] == 3

    # 在庫5を超える更新は拒否される。
    over_res = client.patch(f"/api/cart/items/{cart_item_id}", json={"quantity": 6})
    assert over_res.status_code == 422

    delete_res = client.delete(f"/api/cart/items/{cart_item_id}")
    assert delete_res.status_code == 204

    get_res = client.get("/api/cart")
    assert get_res.json()["items"] == []

    client.cookies.clear()


def test_update_unknown_cart_item_returns_404():
    res = client.patch("/api/cart/items/does-not-exist", json={"quantity": 1})
    assert res.status_code == 404
    assert res.json()["errorCode"] == "CART_ITEM_NOT_FOUND"


def test_delete_unknown_cart_item_returns_404():
    res = client.delete("/api/cart/items/does-not-exist")
    assert res.status_code == 404
