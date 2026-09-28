"""商品情報API。

Frontend側の呼び出し元:
  gu-ec-frontend/app/api/products/[productId]/route.ts             -> GET /api/products/{productId}
  gu-ec-frontend/app/api/products/[productId]/variations/route.ts  -> GET /api/products/{productId}/variations
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app import data
from app.schemas import ErrorResponse, Product, ProductVariation

router = APIRouter(prefix="/api/products", tags=["products"])


def _to_product_schema(record: data.ProductRecord) -> Product:
    return Product(
        product_id=record.product_id,
        name=record.name,
        category=record.category,
        description=record.description,
        material=record.material,
        care_instructions=record.care_instructions,
        country_of_origin=record.country_of_origin,
        base_price=record.base_price,
        discount_rate=record.discount_rate,
        default_size=record.default_size,
        variations=[_to_variation_schema(v) for v in record.variations],
    )


def _to_variation_schema(record: data.VariationRecord) -> ProductVariation:
    return ProductVariation(
        sku_id=record.sku_id,
        product_id=record.product_id,
        color=record.color,
        size=record.size,
        stock_quantity=record.stock_quantity,
    )


@router.get(
    "/{product_id}",
    response_model=Product,
    responses={404: {"model": ErrorResponse}},
)
def get_product(product_id: str) -> Product:
    record = data.get_product(product_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={"errorCode": "PRODUCT_NOT_FOUND", "message": f"商品が見つかりません: {product_id}"},
        )
    return _to_product_schema(record)


@router.get(
    "/{product_id}/variations",
    response_model=list[ProductVariation],
    responses={404: {"model": ErrorResponse}},
)
def list_variations(product_id: str) -> list[ProductVariation]:
    record = data.get_product(product_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={"errorCode": "PRODUCT_NOT_FOUND", "message": f"商品が見つかりません: {product_id}"},
        )
    return [_to_variation_schema(v) for v in record.variations]
