"""カートAPI。

Frontend側の呼び出し元:
  gu-ec-frontend/app/api/cart/route.ts                       -> GET    /api/cart
  gu-ec-frontend/app/api/cart/items/route.ts                 -> POST   /api/cart/items
  gu-ec-frontend/app/api/cart/items/[cartItemId]/route.ts    -> PATCH  /api/cart/items/{cartItemId}
                                                                  DELETE /api/cart/items/{cartItemId}

数量の上限（在庫数・運用上限99）チェックは、設計書
「入力値・数量の制約定義とエラー処理設計」およびFrontend側
app/products/[productId]/page.tsx の OPERATIONAL_MAX_QUANTITY と
一致させている（app/pricing.py 参照）。Frontendのチェックは表示上の簡易チェックであり、
最終的な正としての検証はここ（Backend）で行う。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response

from app import data
from app.config import Settings, get_settings
from app.dependencies import CART_ID_COOKIE_NAME, get_optional_cart_id
from app.pricing import calculate_cart_totals, calculate_final_price, calculate_max_quantity
from app.schemas import (
    CartItemInput,
    CartItemQuantityUpdate,
    CartItemResponse,
    CartLineItem,
    CartResponse,
    ErrorResponse,
)

router = APIRouter(prefix="/api/cart", tags=["cart"])


def _error(status_code: int, error_code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"errorCode": error_code, "message": message})


def _build_cart_response(cart_id: str | None) -> CartResponse:
    if cart_id is None:
        return CartResponse(cart_id=None, items=[], cart_total_quantity=0, cart_total_price=0)

    records = data.get_cart_items(cart_id)
    line_items: list[CartLineItem] = []
    product_cache: dict[str, data.ProductRecord] = {}

    for record in records:
        variation = data.find_variation_by_sku(record.sku_id)
        if variation is None:
            # 商品マスタ側でSKUが削除された等、通常運用では起きない想定だが、
            # カートデータの不整合でクラッシュさせないため読み飛ばす。
            continue
        product = product_cache.get(variation.product_id) or data.get_product(variation.product_id)
        if product is None:
            continue
        product_cache[variation.product_id] = product
        unit_price = calculate_final_price(product)
        line_items.append(
            CartLineItem(
                cart_item_id=record.cart_item_id,
                sku_id=record.sku_id,
                product_id=variation.product_id,
                color=variation.color,
                size=variation.size,
                unit_price=unit_price,
                quantity=record.quantity,
                subtotal=unit_price * record.quantity,
            )
        )

    total_quantity = sum(li.quantity for li in line_items)
    total_price = sum(li.subtotal for li in line_items)
    return CartResponse(
        cart_id=cart_id,
        items=line_items,
        cart_total_quantity=total_quantity,
        cart_total_price=total_price,
    )


@router.get("", response_model=CartResponse)
def get_cart(cart_id: str | None = Depends(get_optional_cart_id)) -> CartResponse:
    return _build_cart_response(cart_id)


@router.post(
    "/items",
    response_model=CartItemResponse,
    status_code=201,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def add_cart_item(
    body: CartItemInput,
    response: Response,
    cart_id: str | None = Depends(get_optional_cart_id),
    settings: Settings = Depends(get_settings),
) -> CartItemResponse:
    variation = data.find_variation_by_sku(body.sku_id)
    if variation is None:
        raise _error(404, "SKU_NOT_FOUND", f"SKUが見つかりません: {body.sku_id}")

    if variation.stock_quantity == 0:
        raise _error(409, "OUT_OF_STOCK", "在庫がありません")

    max_quantity = calculate_max_quantity(variation, settings.operational_max_quantity)

    # cart_idが未発行なら、このリクエストで新規発行してCookieにセットする。
    is_new_cart = cart_id is None
    if is_new_cart:
        cart_id = data.new_cart_id()

    existing = data.find_cart_item_by_sku(cart_id, body.sku_id)
    new_total_quantity = body.quantity + (existing.quantity if existing else 0)

    if new_total_quantity > max_quantity:
        raise _error(
            422,
            "QUANTITY_EXCEEDS_LIMIT",
            f"数量が上限（{max_quantity}）を超えています（在庫数と運用上限99のうち小さい方）",
        )

    # 既存行があれば同じcart_item_idで数量を上書き、無ければ新規行として保存する。
    # （以前は既存行の場合にオブジェクトの値を書き換えるだけでDBへ保存しておらず、
    #   インメモリモードでしか数量が増えなかったため、必ず upsert_cart_item を呼ぶようにした）
    cart_item_id = existing.cart_item_id if existing else data.new_cart_item_id()
    data.upsert_cart_item(
        cart_id,
        data.CartItemRecord(cart_item_id=cart_item_id, sku_id=body.sku_id, quantity=new_total_quantity),
    )

    if is_new_cart:
        response.set_cookie(
            key=CART_ID_COOKIE_NAME,
            value=cart_id,
            httponly=True,
            samesite="lax",
            path="/",
        )

    product = data.get_product(variation.product_id)
    assert product is not None  # find_variation_by_sku経由なら必ず存在する
    unit_price = calculate_final_price(product)
    cart_total_quantity, cart_total_price = calculate_cart_totals(data.get_cart_items(cart_id), product)

    return CartItemResponse(
        cart_id=cart_id,
        cart_item_id=cart_item_id,
        quantity=new_total_quantity,
        subtotal=unit_price * new_total_quantity,
        cart_total_quantity=cart_total_quantity,
        cart_total_price=cart_total_price,
    )


@router.patch(
    "/items/{cart_item_id}",
    response_model=CartItemResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def update_cart_item_quantity(
    cart_item_id: str,
    body: CartItemQuantityUpdate,
    cart_id: str | None = Depends(get_optional_cart_id),
    settings: Settings = Depends(get_settings),
) -> CartItemResponse:
    if cart_id is None:
        raise _error(404, "CART_ITEM_NOT_FOUND", "カートが見つかりません")

    record = data.get_cart_item(cart_id, cart_item_id)
    if record is None:
        raise _error(404, "CART_ITEM_NOT_FOUND", f"カート内商品が見つかりません: {cart_item_id}")

    variation = data.find_variation_by_sku(record.sku_id)
    if variation is None:
        raise _error(404, "SKU_NOT_FOUND", f"SKUが見つかりません: {record.sku_id}")

    max_quantity = calculate_max_quantity(variation, settings.operational_max_quantity)
    if body.quantity > max_quantity:
        raise _error(
            422,
            "QUANTITY_EXCEEDS_LIMIT",
            f"数量が上限（{max_quantity}）を超えています（在庫数と運用上限99のうち小さい方）",
        )

    record.quantity = body.quantity
    # DBモード（sqlite/mysql）でも変更が残るよう、必ず保存する。
    data.upsert_cart_item(cart_id, record)

    product = data.get_product(variation.product_id)
    assert product is not None
    unit_price = calculate_final_price(product)
    cart_total_quantity, cart_total_price = calculate_cart_totals(data.get_cart_items(cart_id), product)

    return CartItemResponse(
        cart_id=cart_id,
        cart_item_id=cart_item_id,
        quantity=record.quantity,
        subtotal=unit_price * record.quantity,
        cart_total_quantity=cart_total_quantity,
        cart_total_price=cart_total_price,
    )


@router.delete(
    "/items/{cart_item_id}",
    status_code=204,
    responses={404: {"model": ErrorResponse}},
)
def delete_cart_item(
    cart_item_id: str,
    cart_id: str | None = Depends(get_optional_cart_id),
) -> Response:
    if cart_id is None or not data.delete_cart_item(cart_id, cart_item_id):
        raise _error(404, "CART_ITEM_NOT_FOUND", f"カート内商品が見つかりません: {cart_item_id}")
    return Response(status_code=204)
