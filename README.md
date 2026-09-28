# gu-ec-backend

GU ECサイト構築（学習用）の Backend。Python / FastAPI。

設計書「GU ECサイト構築 設計書」のBackend API仕様、および
`gu-ec-frontend` 側の `lib/backendProxy.ts` / `app/api/**/route.ts` が
呼び出す前提のエンドポイントに合わせて実装しています。

DBアクセスは **ORMを使わず、生SQLを書く方式**（ローカルはSQLite＝標準ライブラリ`sqlite3`、
AzureはMySQL＝`pymysql`。`app/database.py` で接続先を切り替え）です。2026-09-28に、
学校（Tech0）配布の参考資料「超入門書（AzureDBforMYSQL）」の
`tech0_search` プロジェクトと同じ方式に合わせる形で決定しました。

## 動作モード（DB_BACKEND）

`.env` の `DB_BACKEND` で切り替えます（`.env.example` 参照）。

| DB_BACKEND | 保存先 | 用途 |
| --- | --- | --- |
| `sqlite` | `gu-ec-backend/guec_local.db`（SQLiteファイル） | **ローカル開発（おすすめ）**。Azure不要、再起動してもデータが残る |
| `mysql` | Azure Database for MySQL | 本番・Azure接続時 |
| `memory` | サーバープロセスのメモリ | 自動テスト用（再起動で消える） |

- **SQLiteモード**: `uvicorn` 起動時に、テーブル作成（`schema_sqlite.sql`）と
  ダミー商品データ投入が自動で行われます（既にあればスキップ）。
  DBの中身をリセットしたいときは、サーバーを止めて `guec_local.db` を削除するだけです。
- **Azure MySQLモード**: 下記「Azure Database for MySQLへの接続」の手順が必要です。
- 以前の `USE_MYSQL=true/false` も互換のため引き続き使えます
  （`DB_BACKEND` が未設定のときだけ参照。`true`→mysql、それ以外→memory）。

どのモードでも `app/routers/` 以下のコードは変更不要です（`app/data.py` が
`DB_BACKEND` の値に応じて `sqlite_store.py` / `mysql_store.py` / インメモリに振り分けています）。

### ローカル（SQLite）→ Azure への切り替え

1. 下記「Azure Database for MySQLへの接続」の手順1〜4でDBを用意する
2. `.env` を `DB_BACKEND=mysql` にして `DB_HOST` などを埋める
3. `python seed_data.py` でテーブル作成とデータ投入
4. サーバーを再起動

コードの変更は不要です。ローカルに戻すときは `DB_BACKEND=sqlite` に戻すだけです。
（注: SQLiteに入っているカートの中身はAzureへは移りません。商品データは両方とも
`app/data.py` のダミーデータから投入されるので同じ内容になります。）

## セットアップ（例）

```bash
cd gu-ec-backend
python -m venv .venv
# Windowsの場合: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Windowsの場合: copy .env.example .env
```

`.env.example` は `DB_BACKEND=sqlite` になっているので、そのまま起動すれば
ローカルのSQLiteで動きます（`guec_local.db` が自動で作られます）。
事前にDBファイルだけ作っておきたい場合は `python seed_data.py` でも作成できます。

> Windowsで `pip install -r requirements.txt` が `UnicodeDecodeError: 'cp932' ...` で
> 失敗する場合は、先に `$env:PYTHONUTF8=1`（PowerShell）/ `set PYTHONUTF8=1`（cmd）を
> 実行してから再度インストールしてください（requirements.txt内の日本語コメントが原因）。

## 起動

```bash
uvicorn app.main:app --reload --port 8000
```

`gu-ec-frontend/.env.local` の `BACKEND_API_URL`（既定値 `http://localhost:8000`）と
ポート番号を一致させてください。

起動確認:

```bash
curl http://localhost:8000/healthz
# => {"status":"ok"}
```

## テスト

```bash
pytest
```

`tests/` 配下で、在庫チェック・運用上限99・カート合計計算などの業務ロジック
（`test_products.py` / `test_cart.py`）に加え、SQLite実装（`test_sqlite_store.py`、
一時ファイルの本物のSQLiteでAPIまで通しで確認）、Azure MySQL用のSQL発行内容
（`test_mysql_store.py`、pymysqlをフェイクに差し替えてテスト）、
`DB_BACKEND` による実装の振り分け（`test_data_dispatch.py`）を確認しています
（全36件）。`.env` の `DB_BACKEND` に関係なく、テストは常にインメモリモードで
動きます（`tests/conftest.py`）。ただしAzure MySQLへの実際の疎通確認は
このテストの範囲外です（後述の手順で各自の環境で行ってください）。

## エンドポイント一覧

| メソッド | パス | 説明 |
| --- | --- | --- |
| GET | `/api/products/{productId}` | 商品情報取得 |
| GET | `/api/products/{productId}/variations` | SKU（色×サイズ）一覧取得 |
| GET | `/api/cart` | カート取得（`cart_id` Cookie が無ければ空カートを返す） |
| POST | `/api/cart/items` | カートに追加（初回は `cart_id` Cookie を新規発行） |
| PATCH | `/api/cart/items/{cartItemId}` | カート内商品の数量変更 |
| DELETE | `/api/cart/items/{cartItemId}` | カート内商品の削除 |
| GET | `/healthz` | ヘルスチェック（Azure App Service等向け） |

エラーレスポンスは共通で `{"errorCode": "...", "message": "..."}` の形（`app/schemas.py` の
`ErrorResponse`、`app/main.py` の例外ハンドラ）。主な `errorCode`:

- `PRODUCT_NOT_FOUND` / `SKU_NOT_FOUND` / `CART_ITEM_NOT_FOUND`（404）
- `OUT_OF_STOCK`（409）
- `QUANTITY_EXCEEDS_LIMIT`（422、上限＝在庫数と運用上限99のうち小さい方）

## 環境変数

`.env.example` を参照してください。`app/__init__.py` が起動時に自動で
`.env` を読み込みます（python-dotenv）。

## ディレクトリ構成

```
gu-ec-backend/
  app/
    main.py          FastAPIアプリ本体・CORS・例外ハンドラ・ルーター登録
    config.py        環境変数ベースの設定（ENABLE_API_DOCS等）
    database.py      DB接続の抽象化（DB_BACKEND、SQLite/MySQLそれぞれの接続関数）
    records.py       内部データの型（dataclass）。data.py / sqlite_store.py / mysql_store.py 共通
    schemas.py       APIリクエスト/レスポンスの型定義（Pydantic, camelCase）
    data.py          データアクセスの窓口。DB_BACKENDに応じてインメモリ/sqlite_store/mysql_storeへ振り分け
    sqlite_store.py  ローカルSQLite用の実装（sqlite3で生SQL）＋起動時のテーブル作成・データ投入
    mysql_store.py   Azure Database for MySQL用の実装（pymysqlで生SQL、ORM不使用）
    pricing.py       金額・上限数量の計算ロジック（Frontendの計算式と一致）
    dependencies.py  cart_id Cookieの読み取り
    routers/
      products.py    商品情報API
      cart.py         カートAPI
  tests/
    conftest.py            テストを常にインメモリモードで動かす設定
    test_products.py
    test_cart.py
    test_mysql_store.py    Azure MySQL用SQLのテスト（pymysqlをフェイクに差し替え）
    test_sqlite_store.py   SQLite実装のテスト（一時ファイルの本物のSQLiteを使用）
    test_data_dispatch.py  DB_BACKENDによる実装振り分けのテスト
  schema.sql         Azure Database for MySQL用のテーブル定義（CREATE TABLE）
  schema_sqlite.sql  ローカルSQLite用のテーブル定義（schema.sqlと同じテーブル・列）
  seed_data.py        スキーマ作成＋ダミー商品データ投入スクリプト（DB_BACKENDに応じて投入先が変わる）
  guec_local.db      SQLiteモードで自動生成されるDBファイル（Git管理外）
  requirements.txt
  .env.example
```

---

## Azure Database for MySQLへの接続

学校（Tech0）側で用意されたAzure Database for MySQLサーバーに、自分専用の
データベースを作成して接続します。以下はAzureへのログイン・パスワード入力など
**ご自身の環境で行っていただく必要がある手順**です（Claudeはこの部分を代行できません。
Azureのログイン情報・パスワードはこの会話やコード上には書かないでください）。

### 1. Azureポータルで自分のDBリソースを探す

1. Tech0側から案内されたURLからAzureにログインする。
2. リソース一覧から自分のクラスに対応するDBリソース
   （例: `tech0-search-db-class12`）を探して開く。
3. 「概要」タブに表示される **エンドポイント**（例:
   `tech0-search-db-class12.mysql.database.azure.com`）と、
   「接続」タブに表示される **ユーザー名・パスワード** を控える。

### 2. 自分のIPアドレスをファイアウォールに登録する

1. https://www.whatismyip.com/ 等で自分のグローバルIPv4アドレスを確認する。
2. DBリソース画面の「設定」→「ネットワーク」で、開始IP・終了IPに同じ値を入力し、
   ファイアウォール規則名を自分と分かる名前にして「保存」する。

### 3. CLIで接続テストする（任意だが推奨）

DBリソース画面の「設定」→「接続」に表示されるコマンド例を参考に、
Azure Cloud Shell（またはローカルのmysqlクライアント）から接続できるか確認する。

```
mysql -h <エンドポイント> -P 3306 -u <ユーザー名> -p
```

パスワード入力は反応が無いように見えるが実際は入力されているので、
入力後にEnterを押す。`SHOW DATABASES;` で一覧が表示されれば成功。

### 4. 自分のデータベースを作成する

上記のCLI接続の中で、自分専用のデータベースを作成する
（他の受講者と同じサーバーを共有しているため、名前は自分専用にすること）。

```sql
CREATE DATABASE guec_<自分のユーザー名> CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 5. `.env` を更新する

`gu-ec-backend/.env` を以下のように変更する（`.env.example` のテンプレート参照）。

```
DB_BACKEND=mysql
DB_HOST=<手順1で控えたエンドポイント>
DB_PORT=3306
DB_USER=<手順1で控えたユーザー名>
DB_PASSWORD=<手順1で控えたパスワード>
DB_NAME=guec_<自分のユーザー名>
```

### 6. テーブル作成とダミーデータ投入

```bash
cd gu-ec-backend
python seed_data.py
```

`✅ テーブル作成完了` と `✅ サンプルデータ投入: 商品1件追加 / SKU 6件追加・0件スキップ`
のように表示されれば成功（`schema.sql` の内容でテーブルを作成し、
`app/data.py` のダミー商品データをそのままAzure MySQLへ投入します）。
既に投入済みの場合は「0件追加・6件スキップ」のように表示され、何度実行しても
安全です（冪等）。

### 7. 接続確認

```bash
python -c "from app.database import get_connection; conn = get_connection(); print('接続成功:', conn); conn.close()"
```

その後、`uvicorn app.main:app --reload --port 8000` で起動し、
`curl http://localhost:8000/api/products/prod-001` がAzure MySQL上のデータを
返すことを確認してください（レスポンス内容はローカル簡易モードと同じはずです。
データの取得元だけがインメモリからAzure MySQLに変わっています）。

### 8. Azure CLIでの目視確認（任意）

Cloud Shellで以下を実行し、投入したデータを直接確認できます。

```sql
USE guec_<自分のユーザー名>;
SHOW TABLES;
SELECT COUNT(*) FROM product_variation;
SELECT sku_id, color, size, stock_quantity FROM product_variation;
```
