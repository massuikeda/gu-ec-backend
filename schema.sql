-- gu-ec-backend データベーススキーマ（Azure Database for MySQL用）
--
-- 使い方（README.md「Azure Database for MySQLへの接続」も参照）:
--   1. 自分のデータベースを作成する（例）:
--        CREATE DATABASE guec_<自分のユーザー名> CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
--        USE guec_<自分のユーザー名>;
--   2. このファイルの内容をそのまま実行する（CLIなら `source schema.sql;` でも可）。
--
-- 日本語（商品名・色・カテゴリ等）を扱うため、文字コードは utf8mb4 / utf8mb4_unicode_ci に統一している。

CREATE TABLE IF NOT EXISTS product (
    product_id        VARCHAR(64)  NOT NULL PRIMARY KEY,
    name              VARCHAR(255) NOT NULL,
    category          VARCHAR(100) NOT NULL,
    description       TEXT,
    material          VARCHAR(255),
    care_instructions VARCHAR(255),
    country_of_origin VARCHAR(100),
    base_price        INT          NOT NULL,
    discount_rate     DECIMAL(4,3) NOT NULL DEFAULT 0.000,
    default_size      VARCHAR(20),
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS product_variation (
    sku_id         VARCHAR(64) NOT NULL PRIMARY KEY,
    product_id     VARCHAR(64) NOT NULL,
    color          VARCHAR(50) NOT NULL,
    size           VARCHAR(20) NOT NULL,
    stock_quantity INT         NOT NULL DEFAULT 0,
    CONSTRAINT fk_product_variation_product
        FOREIGN KEY (product_id) REFERENCES product(product_id)
        ON DELETE CASCADE,
    UNIQUE KEY uq_product_variation_color_size (product_id, color, size)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- カートは会員機能が無い前提のため、cart_idは（会員IDではなく）
-- Cookieで払い出す不透明なUUID文字列（app/data.py: new_cart_id()）。
CREATE TABLE IF NOT EXISTS cart_item (
    cart_item_id VARCHAR(64) NOT NULL PRIMARY KEY,
    cart_id      VARCHAR(64) NOT NULL,
    sku_id       VARCHAR(64) NOT NULL,
    quantity     INT         NOT NULL,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_cart_item_variation
        FOREIGN KEY (sku_id) REFERENCES product_variation(sku_id),
    KEY idx_cart_item_cart_id (cart_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
