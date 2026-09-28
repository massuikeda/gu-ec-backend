-- gu-ec-backend データベーススキーマ（ローカルSQLite用）
--
-- Azure Database for MySQL用の schema.sql と同じテーブル・同じ列名にしてある。
-- MySQLとの書き方の違い:
--   - ENGINE / CHARSET 指定は無い（SQLiteは常にUTF-8）
--   - DECIMAL は REAL、VARCHAR(n) は TEXT で扱う
--   - ON UPDATE CURRENT_TIMESTAMP は無いので、更新時は updated_at をSQL側で明示的にセットする
--   - UNIQUE KEY / KEY は UNIQUE制約 / CREATE INDEX で書く
--
-- 通常は手で実行する必要は無い。DB_BACKEND=sqlite で uvicorn を起動すると
-- app/sqlite_store.py の init_db() が自動で実行する（seed_data.py からも実行可能）。

CREATE TABLE IF NOT EXISTS product (
    product_id        TEXT    NOT NULL PRIMARY KEY,
    name              TEXT    NOT NULL,
    category          TEXT    NOT NULL,
    description       TEXT,
    material          TEXT,
    care_instructions TEXT,
    country_of_origin TEXT,
    base_price        INTEGER NOT NULL,
    discount_rate     REAL    NOT NULL DEFAULT 0,
    default_size      TEXT,
    created_at        TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at        TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS product_variation (
    sku_id         TEXT    NOT NULL PRIMARY KEY,
    product_id     TEXT    NOT NULL REFERENCES product(product_id) ON DELETE CASCADE,
    color          TEXT    NOT NULL,
    size           TEXT    NOT NULL,
    stock_quantity INTEGER NOT NULL DEFAULT 0,
    UNIQUE (product_id, color, size)
);

-- カートは会員機能が無い前提のため、cart_idは（会員IDではなく）
-- Cookieで払い出す不透明なUUID文字列（app/data.py: new_cart_id()）。
CREATE TABLE IF NOT EXISTS cart_item (
    cart_item_id TEXT    NOT NULL PRIMARY KEY,
    cart_id      TEXT    NOT NULL,
    sku_id       TEXT    NOT NULL REFERENCES product_variation(sku_id),
    quantity     INTEGER NOT NULL,
    created_at   TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at   TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cart_item_cart_id ON cart_item (cart_id);
