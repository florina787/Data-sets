"""Synthetic product catalog. Prices are integer cents (CAD)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    brand: str
    size: str
    price_cents: int


PRODUCTS: tuple[Product, ...] = (
    Product("FS-MANGO-355", "FreshSip Mango", "FreshSip", "355 mL", 249),
    Product("FS-ORANGE-355", "FreshSip Orange", "FreshSip", "355 mL", 249),
    Product("FS-APPLE-355", "FreshSip Apple", "FreshSip", "355 mL", 249),
    Product("FS-SPARKLIME-355", "FreshSip Sparkling Lime", "FreshSip", "355 mL", 279),
    Product("BH-COLDBREW-300", "Brewhouse Cold Brew", "Brewhouse", "300 mL", 399),
    Product("NT-OATMILK-1L", "NutriTerra Oat Milk", "NutriTerra", "1 L", 449),
)

_BY_SKU = {p.sku: p for p in PRODUCTS}

PROVINCES = ("AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT")


def get_product(sku: str) -> Product:
    try:
        return _BY_SKU[sku]
    except KeyError:
        raise KeyError(f"Unknown SKU: {sku}") from None
