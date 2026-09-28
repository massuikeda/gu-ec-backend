"""Azure Database for MySQL 上のデータアクセス（pymysqlで生SQLを実行）。

ORM（SQLAlchemy等）は使わず、生SQL＋パラメータバインドで書く方針
（設計書「SQLインジェクション対策」、および参考資料 tech0_search/backend の
 database.py / search.py と同じ書き方）。

app/data.py と全く同じ関数シグネチャ・同じdataclass（app/records.py）を実装しており、
routers/ 側は DB_BACKEND が memory/sqlite/mysql のどれでも app.data の関数を呼ぶだけでよい
（app/data.py側でこのモジュールへの委譲を行っている）。
"""

from __future__ import annotations

from app import database
from app.records import CartItemRecord, ProductRecord, VariationRecord


def _row_to_variation(row: dict) -> VariationRecord:
    return VariationRecord(
        sku_id=row["sku_id"],
        product_id=row["product_id"],
        color=row["color"],
        size=row["size"],
        stock_quantity=row["stock_quantity"],
    )


def _row_to_cart_item(row: dict) -> CartItemRecord:
    return CartItemRecord(
        cart_item_id=row["cart_item_id"],
        sku_id=row["sku_id"],
        quantity=row["quantity"],
    )


def get_product(product_id: str) -> ProductRecord | None:
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT product_id, name, category, description, material, "
                "care_instructions, country_of_origin, base_price, discount_rate, default_size "
                "FROM product WHERE product_id = %s",
                (product_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None

            cur.execute(
                "SELECT sku_id, product_id, color, size, stock_quantity "
                "FROM product_variation WHERE product_id = %s",
                (product_id,),
            )
            variations = [_row_to_variation(r) for r in cur.fetchall()]

        return ProductRecord(
            product_id=row["product_id"],
            name=row["name"],
            category=row["category"],
            description=row["description"] or "",
            material=row["material"] or "",
            care_instructions=row["care_instructions"] or "",
            country_of_origin=row["country_of_origin"] or "",
            base_price=row["base_price"],
            discount_rate=float(row["discount_rate"]),
            default_size=row["default_size"],
            variations=variations,
        )
    finally:
        conn.close()


def find_variation_by_sku(sku_id: str) -> VariationRecord | None:
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT sku_id, product_id, color, size, stock_quantity "
                "FROM product_variation WHERE sku_id = %s",
                (sku_id,),
            )
            row = cur.fetchone()
            return _row_to_variation(row) if row else None
    finally:
        conn.close()


def get_cart_items(cart_id: str) -> list[CartItemRecord]:
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT cart_item_id, sku_id, quantity FROM cart_item WHERE cart_id = %s",
                (cart_id,),
            )
            return [_row_to_cart_item(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_cart_item(cart_id: str, cart_item_id: str) -> CartItemRecord | None:
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT cart_item_id, sku_id, quantity FROM cart_item "
                "WHERE cart_id = %s AND cart_item_id = %s",
                (cart_id, cart_item_id),
            )
            row = cur.fetchone()
            return _row_to_cart_item(row) if row else None
    finally:
        conn.close()


def find_cart_item_by_sku(cart_id: str, sku_id: str) -> CartItemRecord | None:
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT cart_item_id, sku_id, quantity FROM cart_item "
                "WHERE cart_id = %s AND sku_id = %s",
                (cart_id, sku_id),
            )
            row = cur.fetchone()
            return _row_to_cart_item(row) if row else None
    finally:
        conn.close()


def upsert_cart_item(cart_id: str, item: CartItemRecord) -> None:
    """cart_item_idが既存なら数量を更新、無ければ新規挿入する。

    ON DUPLICATE KEY UPDATE を使うことで、INSERTとUPDATEを1クエリにまとめている
    （cart_item_idがPRIMARY KEYであることが前提。schema.sql参照）。
    """
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO cart_item (cart_item_id, cart_id, sku_id, quantity) "
                "VALUES (%s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE quantity = VALUES(quantity)",
                (item.cart_item_id, cart_id, item.sku_id, item.quantity),
            )
        conn.commit()
    finally:
        conn.close()


def delete_cart_item(cart_id: str, cart_item_id: str) -> bool:
    conn = database.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM cart_item WHERE cart_id = %s AND cart_item_id = %s",
                (cart_id, cart_item_id),
            )
            deleted = cur.rowcount > 0
        conn.commit()
        return deleted
    finally:
        conn.close()
