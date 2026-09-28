"""データレコードの型（dataclass）。

app/data.py（インメモリ実装）・app/sqlite_store.py（SQLite実装）・app/mysql_store.py（Azure MySQL実装）の
両方が同じdataclassを使うことで、routers/ 側はどちらの実装が動いているか
（DB_BACKEND環境変数の値）を意識せずに済むようにしている。

app/schemas.py（Pydantic, APIの入出力用）とは役割が別。
records.py＝内部のデータ保持用、schemas.py＝APIの境界用。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VariationRecord:
    sku_id: str
    product_id: str
    color: str
    size: str
    stock_quantity: int


@dataclass
class ProductRecord:
    product_id: str
    name: str
    category: str
    description: str
    material: str
    care_instructions: str
    country_of_origin: str
    base_price: int
    discount_rate: float
    default_size: str | None
    variations: list[VariationRecord] = field(default_factory=list)


@dataclass
class CartItemRecord:
    cart_item_id: str
    sku_id: str
    quantity: int
