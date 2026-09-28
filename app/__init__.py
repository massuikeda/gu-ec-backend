"""GU ECサイト構築 - Backend (FastAPI)

このパッケージがFastAPIアプリケーション本体。
設計書「GU ECサイト構築 設計書」のBackend REST API層に対応する。

.envファイルの読み込み（python-dotenv）をここで一度だけ行う。
app.database がDB_BACKEND等の環境変数をモジュール読み込み時に見るため、
（サブモジュールの中で一番最初に必ず実行される）このパッケージの
__init__.py で読み込んでおく必要がある。

データの実体は、DB_BACKEND環境変数に応じて以下のいずれかに切り替わる
（詳細はapp/data.pyのdocstring参照）。
  - memory : インメモリ辞書（再起動で消える。主にテスト用）
  - sqlite : ローカルのSQLiteファイル（app/sqlite_store.py、ローカル開発用）
  - mysql  : Azure Database for MySQL（app/mysql_store.py、pymysqlで生SQL）
ORM（SQLAlchemy等）は使わない方針とした（2026-09-28決定）。
"""

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # python-dotenvが未インストールでも、OS側で環境変数を設定していれば動作する。
    pass
