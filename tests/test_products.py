"""商品API（app/routers/products.py）のテスト。"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_product_success():
    res = client.get("/api/products/prod-001")
    assert res.status_code == 200
    body = res.json()
    assert body["productId"] == "prod-001"
    assert body["name"] == "スウェットプルパーカ"
    assert len(body["variations"]) == 6


def test_get_product_not_found():
    res = client.get("/api/products/does-not-exist")
    assert res.status_code == 404
    body = res.json()
    assert body["errorCode"] == "PRODUCT_NOT_FOUND"


def test_list_variations_success():
    res = client.get("/api/products/prod-001/variations")
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body, list)
    sku_ids = {v["skuId"] for v in body}
    assert sku_ids == {"sku-001", "sku-002", "sku-003", "sku-004", "sku-005", "sku-006"}


def test_list_variations_not_found():
    res = client.get("/api/products/does-not-exist/variations")
    assert res.status_code == 404
