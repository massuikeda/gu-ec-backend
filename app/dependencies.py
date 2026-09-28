"""FastAPIの依存性注入（Depends）でルーター間で共有する処理。

カートはCookie（cart_id）で識別する。
Frontendの lib/backendProxy.ts はブラウザのCookieヘッダーをそのまま
Backendへ中継する設計になっているため、Backend側はCookieを見るだけでよい
（Next.js側でcart_idを意識する必要はない）。
"""

from __future__ import annotations

from fastapi import Cookie

CART_ID_COOKIE_NAME = "cart_id"


def get_optional_cart_id(cart_id: str | None = Cookie(default=None, alias=CART_ID_COOKIE_NAME)) -> str | None:
    """Cookieにcart_idがあれば返す。無ければNone（＝空のカート扱い）。

    GET /api/cart のように、カートが無くてもエラーにせず空カートを返したい場合に使う。
    """
    return cart_id
