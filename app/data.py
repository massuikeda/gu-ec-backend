"""データアクセスの窓口（routers/ 側が実際に呼び出すモジュール）。

DB_BACKEND環境変数（app/database.py参照）に応じて、実データを次のどこから読み書きするかを
このモジュール内で振り分けている。

  memory : このファイル内のインメモリ辞書（再起動で消える。主にテスト用）
  sqlite : ローカルのSQLiteファイル（app/sqlite_store.py）
  mysql  : Azure Database for MySQL（app/mysql_store.py、pymysqlで生SQL）

routers/products.py・routers/cart.py はこのモジュールの関数だけを呼び、
DB_BACKENDの値を意識しない（設計書のとおり、DBアクセス方式が変わっても
routers/ 以下は変更不要にする狙い）。
sqlite_store.py と mysql_store.py は全く同じ関数名・引数・戻り値の型を持っているので、
_store() でモジュールを選んで同じ関数を呼ぶだけで切り替えられる。

【SQLiteモード（DB_BACKEND=sqlite、ローカル開発用）】
  gu-ec-backend/guec_local.db に保存される（再起動しても残る）。
  起動時にテーブル作成とダミー商品データ投入が自動で行われる（app/main.py参照）。

【Azure Database for MySQLモード（DB_BACKEND=mysql）】
  事前に seed_data.py でテーブル作成と商品データ投入をしておく必要がある（README.md参照）。
"""

from __future__ import annotations

import threading
import uuid

from app import database
from app.records import CartItemRecord, ProductRecord, QuantityExceedsLimitError, VariationRecord

# --- ローカル簡易モード用のダミーデータ ------------------------------------
# Frontend側 data/dummyProducts.ts と同じ商品・SKU構成。
# SQLite / Azure MySQLモードでは、このデータがそのままDBに投入される（seed_data.py / sqlite_store.init_db）。

_PRODUCT = ProductRecord(
    product_id="prod-001",
    name="スウェットプルパーカ",
    category="トップス",
    description="肉厚な裏毛素材を使用したリラックスフィットのパーカ。",
    material="綿80% ポリエステル20%",
    care_instructions="洗濯機の使用可（ネット使用推奨）",
    country_of_origin="中国",
    base_price=2990,
    discount_rate=0,
    default_size="M",
    variations=[
        VariationRecord("sku-001", "prod-001", "ブラック", "S", 5),
        VariationRecord("sku-002", "prod-001", "ブラック", "M", 0),
        VariationRecord("sku-003", "prod-001", "ブラック", "L", 120),
        VariationRecord("sku-004", "prod-001", "ホワイト", "S", 3),
        VariationRecord("sku-005", "prod-001", "ホワイト", "M", 8),
        VariationRecord("sku-006", "prod-001", "ホワイト", "L", 0),
    ],
)

# product_id -> ProductRecord。商品は今のところ1点のみだが、
# 将来の商品追加に備えて辞書構造にしてある。
PRODUCTS: dict[str, ProductRecord] = {_PRODUCT.product_id: _PRODUCT}

# cart_id -> cart_item_id -> CartItemRecord （ローカル簡易モードのみで使用）
CART_STORE: dict[str, dict[str, CartItemRecord]] = {}

# インメモリモードで add_quantity を同時実行しても上限を超えないようにするためのロック
_CART_LOCK = threading.Lock()


def new_cart_id() -> str:
    """新しいcart_idを発行する（Cookieに入れて返す値）。DBモードに関わらず共通。"""
    return uuid.uuid4().hex


def new_cart_item_id() -> str:
    return uuid.uuid4().hex


def get_local_dummy_product() -> ProductRecord:
    """ローカル簡易モードで使っているダミー商品データを返す。

    seed_data.py / sqlite_store.init_db() がDBへ同じ内容を投入する際に、
    このダミーデータを1か所（このファイル）だけで管理するために公開している。
    """
    return _PRODUCT


# --- ここから、DB_BACKENDに応じて実装を振り分ける関数群 ---------------------


def _store():
    """DB_BACKENDに応じたストアモジュールを返す。インメモリの場合はNone。"""
    if database.DB_BACKEND == "mysql":
        from app import mysql_store

        return mysql_store
    if database.DB_BACKEND == "sqlite":
        from app import sqlite_store

        return sqlite_store
    return None


def get_product(product_id: str) -> ProductRecord | None:
    store = _store()
    if store is not None:
        return store.get_product(product_id)
    return PRODUCTS.get(product_id)


def find_variation(product_id: str, sku_id: str) -> VariationRecord | None:
    product = get_product(product_id)
    if product is None:
        return None
    for variation in product.variations:
        if variation.sku_id == sku_id:
            return variation
    return None


def find_variation_by_sku(sku_id: str) -> VariationRecord | None:
    """商品を横断してsku_idからバリエーションを探す（カートAPIはproduct_idを受け取らないため）。"""
    store = _store()
    if store is not None:
        return store.find_variation_by_sku(sku_id)
    for product in PRODUCTS.values():
        for variation in product.variations:
            if variation.sku_id == sku_id:
                return variation
    return None


def get_cart_items(cart_id: str) -> list[CartItemRecord]:
    store = _store()
    if store is not None:
        return store.get_cart_items(cart_id)
    return list(CART_STORE.get(cart_id, {}).values())


def get_cart_item(cart_id: str, cart_item_id: str) -> CartItemRecord | None:
    store = _store()
    if store is not None:
        return store.get_cart_item(cart_id, cart_item_id)
    return CART_STORE.get(cart_id, {}).get(cart_item_id)


def find_cart_item_by_sku(cart_id: str, sku_id: str) -> CartItemRecord | None:
    store = _store()
    if store is not None:
        return store.find_cart_item_by_sku(cart_id, sku_id)
    for item in CART_STORE.get(cart_id, {}).values():
        if item.sku_id == sku_id:
            return item
    return None


def upsert_cart_item(cart_id: str, item: CartItemRecord) -> None:
    store = _store()
    if store is not None:
        store.upsert_cart_item(cart_id, item)
        return
    CART_STORE.setdefault(cart_id, {})[item.cart_item_id] = item


def delete_cart_item(cart_id: str, cart_item_id: str) -> bool:
    store = _store()
    if store is not None:
        return store.delete_cart_item(cart_id, cart_item_id)
    cart = CART_STORE.get(cart_id)
    if cart is None or cart_item_id not in cart:
        return False
    del cart[cart_item_id]
    return True


def add_quantity(cart_id: str, sku_id: str, quantity: int, max_quantity: int) -> CartItemRecord:
    """カートに数量を追加する（既に同じSKUがあれば数量を加算）。

    「カート内の現在数量を読む → 上限チェック → 保存」を1つの排他区間で行う。
    別々に呼ぶと、同時に届いた2つのリクエストがどちらも「まだ0個」と判断して
    両方保存され、上限（在庫数）を超えてしまうため（テスト仕様書 DATA-03）。

    上限を超える場合は QuantityExceedsLimitError を送出し、何も保存しない。
    """
    store = _store()
    if store is not None:
        return store.add_quantity(cart_id, sku_id, quantity, max_quantity, new_cart_item_id())
    with _CART_LOCK:
        existing = find_cart_item_by_sku(cart_id, sku_id)
        new_total = quantity + (existing.quantity if existing else 0)
        if new_total > max_quantity:
            raise QuantityExceedsLimitError()
        item = CartItemRecord(
            cart_item_id=existing.cart_item_id if existing else new_cart_item_id(),
            sku_id=sku_id,
            quantity=new_total,
        )
        CART_STORE.setdefault(cart_id, {})[item.cart_item_id] = item
        return item
