"""DB接続の抽象化レイヤー。

DB_BACKEND 環境変数で、データの保存先を次の3つから切り替える。

  memory : インメモリ辞書（app/data.py 内）。再起動で消える。主にテスト用。
  sqlite : ローカルのSQLiteファイル（app/sqlite_store.py、標準ライブラリsqlite3で生SQL）。
           Azureが無くても永続化つきで動作確認できる。ローカル開発ではこれを使う。
  mysql  : Azure Database for MySQL（app/mysql_store.py、pymysqlで生SQL）。

参考資料（Tech0 提供の tech0_search/backend/database.py）と同じく、
「ローカルはSQLite、本番はAzure MySQL」を環境変数1つで切り替える考え方。

【後方互換】以前の USE_MYSQL=true/false も引き続き使える。
DB_BACKEND が未設定の場合に限り、USE_MYSQL=true なら mysql、それ以外は memory とみなす。
"""

from __future__ import annotations

import os
import pathlib
import sqlite3

VALID_BACKENDS = ("memory", "sqlite", "mysql")

# プロジェクトのルートディレクトリ（gu-ec-backend/）。
# SQLITE_PATH を相対パスで指定した場合はここを基準にする
# （uvicornをどのディレクトリから起動しても同じDBファイルを使うため）。
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _is_true(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes")


def _resolve_backend() -> str:
    raw = (os.environ.get("DB_BACKEND") or "").strip().lower()
    if not raw:
        # 旧設定（USE_MYSQL）との互換。
        return "mysql" if _is_true(os.environ.get("USE_MYSQL")) else "memory"
    if raw not in VALID_BACKENDS:
        raise ValueError(
            f"DB_BACKEND='{raw}' は不正な値です。{' / '.join(VALID_BACKENDS)} のいずれかを指定してください。"
        )
    return raw


# どのストア（app/data.py内のインメモリ / sqlite_store / mysql_store）を使うかを決める値。
# モジュール読み込み時に一度だけ環境変数を読む
# （テストで切り替えたい場合は、この属性を unittest.mock.patch.object で書き換えること）。
DB_BACKEND = _resolve_backend()

# 旧コードとの互換のために残している（新規コードでは DB_BACKEND を見ること）。
USE_MYSQL = DB_BACKEND == "mysql"


# --- SQLite -----------------------------------------------------------------


def get_sqlite_path() -> pathlib.Path:
    """SQLiteファイルのパス。既定は gu-ec-backend/guec_local.db 。"""
    path = pathlib.Path(os.environ.get("SQLITE_PATH") or "guec_local.db")
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def get_sqlite_connection() -> sqlite3.Connection:
    """ローカルSQLiteへの接続を1つ返す（呼び出し側でclose()すること）。

    - row_factory=sqlite3.Row にしているので、row["列名"] で値を取り出せる
      （pymysqlのDictCursorと同じ書き方ができる）。
    - SQLiteは既定で外部キー制約が無効なので、接続ごとに有効化する。
    """
    conn = sqlite3.connect(get_sqlite_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# --- Azure Database for MySQL ----------------------------------------------


def get_connection():
    """Azure Database for MySQLへの接続を1つ返す（呼び出し側でclose()すること）。

    前提: DB_BACKEND=mysql、かつ以下の環境変数が設定済みであること
    （.env.example参照。値は各自のAzureリソースの「接続」画面に表示されるもの）。
      DB_HOST     例: tech0-search-db-class12.mysql.database.azure.com
      DB_PORT     省略時は3306
      DB_USER     例: admin_class12
      DB_PASSWORD 配布されたパスワード
      DB_NAME     CREATE DATABASE で自分が作成したデータベース名
    """
    # pymysqlはMySQLモードでしか使わないので、ここで遅延importする
    # （SQLite/インメモリモードではpymysqlが無くても起動できるようにするため）。
    import pymysql
    from pymysql.cursors import DictCursor

    return pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        charset="utf8mb4",
        cursorclass=DictCursor,
        # Azure Database for MySQL はSSL接続必須（ssl-mode=require）。
        # pymysqlではssl_disabled=Falseを明示することでSSL接続として扱われる。
        ssl={"ssl_disabled": False},
    )
