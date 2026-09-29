"""DBへ、スキーマ作成＋ダミー商品データの投入を行うスクリプト。

参考資料（tech0_search/backend/seed_data.py）と同じ役割。
.env の DB_BACKEND に応じて投入先が変わる。

  DB_BACKEND=sqlite : ローカルのSQLiteファイル（schema_sqlite.sql を使用）
  DB_BACKEND=mysql  : Azure Database for MySQL（schema.sql を使用）

実行するだけでテーブルが無ければ作成し、商品データが無ければ投入する
（既に存在する場合はスキップするので、何度実行しても安全＝冪等）。

実行方法:
    python seed_data.py

補足:
    SQLiteモードでは uvicorn 起動時にも同じ処理が自動で走るので、
    このスクリプトの実行は必須ではない（DBファイルを先に作っておきたいとき用）。
    MySQLモードでは .env に DB_HOST/DB_USER/DB_PASSWORD/DB_NAME の設定が必要。
"""

from __future__ import annotations

import os
import pathlib

import app  # noqa: F401  .env の読み込み（app/__init__.py）を確実に先に実行する
from app import data, database


def _run_schema(conn) -> None:
    schema_path = pathlib.Path(__file__).parent / "schema.sql"
    sql_text = schema_path.read_text(encoding="utf-8")
    # 先に「--」で始まるコメント行を取り除いてから ";" で分割する。
    # （コメント内にも「source schema.sql;」等の ";" があるため、先に分割すると
    #   コメントの途中で文が切れて構文エラー（1064）になる）
    # ※ スキーマ内にストアドプロシージャや、文字列リテラル内の ";" は無い前提。
    sql_without_comments = "\n".join(
        line for line in sql_text.splitlines() if not line.lstrip().startswith("--")
    )
    statements = [s.strip() for s in sql_without_comments.split(";") if s.strip()]
    with conn.cursor() as cur:
        for statement in statements:
            cur.execute(statement)
    conn.commit()
    print(f"✅ テーブル作成完了（{len(statements)}文実行）")


def _seed_product(conn) -> None:
    product = data.get_local_dummy_product()  # ローカル簡易モードで使っているダミー商品データをそのまま流用する

    with conn.cursor() as cur:
        cur.execute(
            "INSERT IGNORE INTO product "
            "(product_id, name, category, description, material, care_instructions, "
            " country_of_origin, base_price, discount_rate, default_size) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
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
            cur.execute(
                "INSERT IGNORE INTO product_variation "
                "(sku_id, product_id, color, size, stock_quantity) "
                "VALUES (%s, %s, %s, %s, %s)",
                (v.sku_id, v.product_id, v.color, v.size, v.stock_quantity),
            )
            variation_inserted += cur.rowcount

    conn.commit()
    variation_skipped = len(product.variations) - variation_inserted
    print(
        f"✅ サンプルデータ投入: 商品 {product_inserted}件追加 / "
        f"SKU {variation_inserted}件追加・{variation_skipped}件スキップ（重複）"
    )


def main() -> None:
    if database.DB_BACKEND == "sqlite":
        from app import sqlite_store

        sqlite_store.init_db(verbose=True)
        print(f"完了！ SQLiteファイル '{database.get_sqlite_path()}' にデータを投入しました")
        return

    if database.DB_BACKEND != "mysql":
        raise SystemExit(
            f"DB_BACKEND={database.DB_BACKEND} になっています。.env で DB_BACKEND=sqlite "
            "または DB_BACKEND=mysql を指定してください（memoryモードは投入不要です）。"
        )

    conn = database.get_connection()
    try:
        _run_schema(conn)
        _seed_product(conn)
    finally:
        conn.close()

    print(f"完了！ Azure MySQL の DB_NAME='{os.environ.get('DB_NAME')}' にデータを投入しました")


if __name__ == "__main__":
    main()
