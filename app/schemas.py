"""APIリクエスト／レスポンスの型定義（Pydantic）。

設計書「型定義（Frontend TypeScript／Backend Python）」に対応するBackend側の定義。
Frontendの types/product.ts・contexts/CartContext.tsx はcamelCaseのプロパティ名を使うため、
Python側はsnake_caseで書きつつ、JSONとしての入出力はcamelCaseになるよう
alias_generator=to_camel を指定している（Backend・Frontend間の型不整合防止）。

ORM（DBモデル）は2026-09-27時点で未確定。ここで定義しているのはあくまで
APIの境界（リクエスト／レスポンス）の型であり、DBモデルとは独立している。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """JSON入出力をcamelCaseにする共通ベースクラス。"""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


# --- 商品関連 -----------------------------------------------------------


class ProductVariation(CamelModel):
    """1つのSKU（色×サイズ）を表す。data/dummyProducts.ts の ProductVariation 型に対応。"""

    sku_id: str
    product_id: str
    color: str
    size: str
    stock_quantity: int


class Product(CamelModel):
    """商品本体。types/product.ts の Product 型に対応。"""

    product_id: str
    name: str
    category: str
    description: str
    material: str
    care_instructions: str
    country_of_origin: str
    base_price: int
    discount_rate: float
    default_size: str | None = None
    variations: list[ProductVariation]


# --- カート関連 -----------------------------------------------------------


class CartItemInput(CamelModel):
    """POST /api/cart/items のリクエストボディ。"""

    sku_id: str
    # 1 <= quantity。上限（在庫数・運用上限99）はSKUごとに異なるため、
    # ここでは下限のみをPydanticで検証し、上限はbusiness ロジック側（cart_service.py）で検証する。
    quantity: int = Field(ge=1)


class CartItemQuantityUpdate(CamelModel):
    """PATCH /api/cart/items/{cartItemId} のリクエストボディ。"""

    quantity: int = Field(ge=1)


class CartItemResponse(CamelModel):
    """カート追加／更新APIのレスポンス。設計書 paragraph 46 の例に対応する型。"""

    cart_id: str
    cart_item_id: str
    quantity: int
    subtotal: int
    cart_total_quantity: int
    cart_total_price: int


class CartLineItem(CamelModel):
    """GET /api/cart の中の1行（カート内商品明細）。"""

    cart_item_id: str
    sku_id: str
    product_id: str
    color: str
    size: str
    unit_price: int
    quantity: int
    subtotal: int


class CartResponse(CamelModel):
    """GET /api/cart のレスポンス。"""

    cart_id: str | None
    items: list[CartLineItem]
    cart_total_quantity: int
    cart_total_price: int


class ErrorResponse(CamelModel):
    """エラーレスポンス共通形式。Frontendのproxy(lib/backendProxy.ts)が返す
    {errorCode, message} と同じ形にして、フロント側のエラーハンドリングを一本化する。
    """

    error_code: str
    message: str
