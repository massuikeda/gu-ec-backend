"""環境変数ベースの設定。

.env ファイルの読み込み（python-dotenv）は app/__init__.py で行っている
（このモジュールはos.environを読むだけで、dotenv自体は扱わない）。

利用側（main.py 等）は import 時ではなく、
get_settings() を呼んだタイミングで環境変数を読む
（テストやローカル実行で環境変数を切り替えやすくするため）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _split_csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    # Next.js（Route Handler）からのみアクセスされる想定のため、
    # 本番ではCORS自体は不要（同一オリジン経由）。
    # ただしローカルでのSwagger UI確認や、将来的な直接アクセス調査用に
    # 環境変数で明示的に許可した場合のみCORSを有効化する。
    allowed_origins: list[str] = field(
        default_factory=lambda: _split_csv(os.environ.get("ALLOWED_ORIGINS", ""))
    )

    # 設計書「セキュリティ設計」記載の通り、API定義書（Swagger UI/OpenAPI Docs）は
    # 開発環境でのみ有効化する。本番では既定でオフ。
    enable_api_docs: bool = field(
        default_factory=lambda: os.environ.get("ENABLE_API_DOCS", "false").lower()
        in ("1", "true", "yes")
    )

    # 運用上限（設計書「入力値・数量の制約定義とエラー処理設計」に対応）。
    # Frontend側 OPERATIONAL_MAX_QUANTITY (app/products/[productId]/page.tsx) と同じ値を維持すること。
    operational_max_quantity: int = field(
        default_factory=lambda: int(os.environ.get("OPERATIONAL_MAX_QUANTITY", "99"))
    )


def get_settings() -> Settings:
    return Settings()
