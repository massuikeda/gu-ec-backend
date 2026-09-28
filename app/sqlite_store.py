"""ローカルSQLite上のデータアクセス（標準ライブラリ sqlite3 で生SQLを実行）。

app/mysql_store.py（Azure Database for MySQL版）と全く同じ関数シグネチャ・
同じdataclass（app/records.py）を実装している。
routers/ 側は DB_BACKEND が sqlite / mysql のどちらでも app.data の関数を呼ぶだけでよい。

mysql_store.py との主な違い（SQLの方言差）:
  - プレースホルダが %s ではなく ?
  - INSERT IGNORE             -> INSERT OR IGNORE
  - ON DUPLICATE KEY UPDATE   -> ON CONFLICT(...) DO UPDATE
  - with conn.cursor() は使えないので conn.execute() を直接呼ぶ
"""

from __future__ import annotations

import pathlib

from app import database
from app.records import CartItemRecord, ProductRecord, VariationRecord

SCHEMA_PATH = database.PROJECT_ROOT / "schema_sqlite.sql"


def _row_to_variation(row) -> VariationRecord:
    return VariationRecord(
        sku_id=row["sku_id"],
        product_id=row["product_id"],
        color=row["color"],
        size=row["size"],
        stock_quantity=row["stock_quantity"],
    )


def _row_to_cart_item(row) -> CartItemRecord:
    return CartItemRecord(
        cart_item_id=row["cart_item_id"],
        sku_id=row["sku_id"],
        quantity=row["quantity"],
    )


# --- 初期化（テーブル作成＋ダミーデータ投入） ------------------------------


def init_db(verbose: bool = False) -> tuple[int, int]:
    """テーブルが無ければ作成し、ダミー商品データが無ければ投入する（何度実行しても安全＝冪等）。

    戻り値: (追加した商品数, 追加したSKU数)
    """
    # 循環importを避けるため関数内でimportする（app.data は app.sqlite_store を参照するため）。
    from app import data

    db_path = database.get_sqlite_path()
    pathlib.Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = database.get_sqlite_connection()
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

        product = data.get_local_dummy_product()
        cur = conn.execute(
            "INSERT OR IGNORE INTO product "
            "(product_id, name, category, description, material, care_instructions, "
            " country_of_origin, base_price, discount_rate, default_size) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                product.product_id,
                product.name,
                product.category,
                product.description,
                product.material,
                product.care_instructions,
                product.country_of_origin,
                product.base_price,
                product.discount_rate,
                product.default_size,
            ),
        )
        product_inserted = cur.rowcount

        variation_inserted = 0
        for v in product.variations:
            cur = conn.execute(
                "INSERT OR IGNORE INTO product_variation "
                "(sku_id, product_id, color, size, stock_quantity) "
                "VALUES (?, ?, ?, ?, ?)",
                (v.sku_id, v.product_id, v.color, v.size, v.stock_quantity),
            )
            variation_inserted += cur.rowcount

        conn.commit()
    finally:
        conn.close()

    if verbose:
        skipped = len(product.variations) - variation_inserted
        print(f"✅ SQLiteテーブル作成完了（{db_path}）")
        print(
            f"✅ サンプルデータ投入: 商品 {product_inserted}件追加 / "
            f"SKU {variation_inserted}件追加・{skipped}件スキップ（重複）"
        )
    return product_inserted, variation_inserted


# --- データアクセス（mysql_store.py と同じ関数群） -------------------------


def get_product(product_id: str) -> ProductRecord | None:
    conn = database.get_sqlite_connection()
    try:
        row = conn.execute(
            "SELECT product_id, name, category, description, material, "
            "care_instructions, country_of_origin, base_price, discount_rate, default_size "
            "FROM product WHERE product_id = ?",
            (product_id,),
        ).fetchone()
        if row is None:
            return None

        variations = [
            _row_to_variation(r)
            for r in conn.execute(
                "SELECT sku_id, product_id, color, size, stock_quantity "
                "FROM product_variation WHERE product_id = ? ORDER BY sku_id",
                (product_id,),
            ).fetchall()
        ]

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
    conn = database.get_sqlite_connection()
    try:
        row = conn.execute(
            "SELECT sku_id, product_id, color, size, stock_quantity "
            "FROM product_variation WHERE sku_id = ?",
            (sku_id,),
        ).fetchone()
        return _row_to_variation(row) if row else None
    finally:
        conn.close()


def get_cart_items(cart_id: str) -> list[CartItemRecord]:
    conn = database.get_sqlite_connection()
    try:
        rows = conn.execute(
            "SELECT cart_item_id, sku_id, quantity FROM cart_item "
            "WHERE cart_id = ? ORDER BY created_at, rowid",
            (cart_id,),
        ).fetchall()
        return [_row_to_cart_item(r) for r in rows]
    finally:
        conn.close()


def get_cart_item(cart_id: str, cart_item_id: str) -> CartItemRecord | None:
    conn = database.get_sqlite_connection()
    try:
        row = conn.execute(
            "SELECT cart_item_id, sku_id, quantity FROM cart_item "
            "WHERE cart_id = ? AND cart_item_id = ?",
            (cart_id, cart_item_id),
        ).fetchone()
        return _row_to_cart_item(row) if row else None
    finally:
        conn.close()


def find_cart_item_by_sku(cart_id: str, sku_id: str) -> CartItemRecord | None:
    conn = database.get_sqlite_connection()
    try:
        row = conn.execute(
            "SELECT cart_item_id, sku_id, quantity FROM cart_item "
            "WHERE cart_id = ? AND sku_id = ?",
            (cart_id, sku_id),
        ).fetchone()
        return _row_to_cart_item(row) if row else None
    finally:
        conn.close()


def upsert_cart_item(cart_id: str, item: CartItemRecord) -> None:
    """cart_item_idが既存なら数量を更新、無ければ新規挿入する。

    MySQL版の ON DUPLICATE KEY UPDATE に相当する、SQLiteの ON CONFLICT ... DO UPDATE を使う。
    """
    conn = database.get_sqlite_connection()
    try:
        conn.execute(
            "INSERT INTO cart_item (cart_item_id, cart_id, sku_id, quantity) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(cart_item_id) DO UPDATE SET "
            "quantity = excluded.quantity, updated_at = CURRENT_TIMESTAMP",
            (item.cart_item_id, cart_id, item.sku_id, item.quantity),
        )
        conn.commit()
    finally:
        conn.close()


def delete_cart_item(cart_id: str, cart_item_id: str) -> bool:
    conn = database.get_sqlite_connection()
    try:
        cur = conn.execute(
            "DELETE FROM cart_item WHERE cart_id = ? AND cart_item_id = ?",
            (cart_id, cart_item_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
