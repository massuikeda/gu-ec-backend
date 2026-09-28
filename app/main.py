"""FastAPIアプリケーションのエントリーポイント。

ローカル起動（例）:
    uvicorn app.main:app --reload --port 8000

Frontend側 .env.local の BACKEND_API_URL (デフォルト http://localhost:8000) と
ポート番号を一致させること。
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import database
from app.config import get_settings
from app.routers import cart, products

_settings = get_settings()

# 設計書「セキュリティ設計」：API定義書（Swagger UI / OpenAPI Docs）は
# 開発環境でのみ有効化する（ENABLE_API_DOCS=true の場合のみ）。
_docs_url = "/docs" if _settings.enable_api_docs else None
_redoc_url = "/redoc" if _settings.enable_api_docs else None
_openapi_url = "/openapi.json" if _settings.enable_api_docs else None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """起動時の処理。

    DB_BACKEND=sqlite の場合、テーブル作成とダミー商品データの投入を自動で行う
    （既にあればスキップ＝冪等なので、毎回実行しても安全）。
    Azure MySQL（DB_BACKEND=mysql）の場合は共有サーバーのため自動では何もせず、
    seed_data.py を手動で実行する運用とする（README.md参照）。
    """
    if database.DB_BACKEND == "sqlite":
        from app import sqlite_store

        sqlite_store.init_db()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="GU ECサイト構築 Backend API",
    version="0.1.0",
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
)

# Next.jsのRoute Handler経由（同一オリジン）が正規のアクセス経路なので、
# 本来CORSは不要。ALLOWED_ORIGINSを明示的に設定した場合のみ、
# ローカルでの直接疎通確認などのために許可する。
if _settings.allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """{"errorCode": ..., "message": ...} をトップレベルのJSONとして返す。

    FastAPIの既定動作は {"detail": {...}} のようにdetailの下にネストしてしまうが、
    Frontend側 lib/backendProxy.ts の BACKEND_UNREACHABLE エラーと同じ形
    （{errorCode, message} をトップレベルに持つ）に揃えることで、
    Frontend側のエラーハンドリングを一本化できるようにしている。
    """
    if isinstance(exc.detail, dict) and "errorCode" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    # 想定外の形式（バリデーションエラー等）は従来通りdetailに包んで返す。
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/healthz", tags=["meta"])
def healthz() -> dict[str, str]:
    """Azure App Service等のヘルスチェック用エンドポイント。"""
    return {"status": "ok"}


app.include_router(products.router)
app.include_router(cart.router)
