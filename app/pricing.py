"""金額・数量に関する業務ロジック。

設計書「入力値・数量の制約定義とエラー処理設計」に対応。
Frontend側 app/products/[productId]/page.tsx の
finalPrice / maxQuantity の計算式と完全に一致させ、
Frontend（表示用の簡易バリデーション）とBackend（正式な検証・再計算）の
金額・上限数量に食い違いが出ないようにしている。
"""

from __future__ import annotations

from app.data import CartItemRecord, ProductRecord, VariationRecord


def calculate_final_price(product: ProductRecord) -> int:
    """値引後の単価。Frontend: Math.round(basePrice * (1 - discountRate)) と同じ式。"""
    return round(product.base_price * (1 - product.discount_rate))


def calculate_max_quantity(variation: VariationRecord, operational_max_quantity: int) -> int:
    """1SKUあたりの上限数量 = min(在庫数, 運用上限)。

    Frontend: Math.min(selectedVariation?.stockQuantity ?? 1, OPERATIONAL_MAX_QUANTITY) と同じ式。
    """
    return min(variation.stock_quantity, operational_max_quantity)


def calculate_cart_totals(
    items: list[CartItemRecord],
    product: ProductRecord,
) -> tuple[int, int]:
    """カート全体の合計数量・合計金額を計算する。

    戻り値: (cart_total_quantity, cart_total_price)
    """
    unit_price = calculate_final_price(product)
    total_quantity = sum(item.quantity for item in items)
    total_price = sum(item.quantity * unit_price for item in items)
    return total_quantity, total_price
