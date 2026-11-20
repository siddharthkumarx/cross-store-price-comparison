"""Typed records shared by the pipeline stages (the validation rules live here)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from crossprice.gtin import check_digit_ok

Availability = Literal["in_stock", "out_of_stock"]


class OfferRow(BaseModel):
    """One variant at one retailer, as observed in one run. Prices are integer US cents."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    retailer_id: str = Field(min_length=1, max_length=64)
    product_id: int = Field(gt=0)
    variant_id: int = Field(gt=0)
    handle: str = Field(min_length=1, max_length=255)
    brand: str = Field(max_length=255)
    product_type: str = Field(max_length=255)
    product_title: str = Field(max_length=255)
    variant_title: str = Field(max_length=255)
    options: tuple[str, ...] = Field(max_length=3)
    sku: str = Field(max_length=255)
    gtin14: str | None = Field(default=None, pattern=r"^[0-9]{14}$")
    price_cents: int = Field(gt=0)
    compare_at_cents: int | None = Field(default=None, gt=0)
    availability: Availability
    observed_at: AwareDatetime

    @field_validator("observed_at")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        if value.utcoffset() != timedelta(0):
            raise ValueError("observed_at must be UTC")
        return value

    @field_validator("gtin14")
    @classmethod
    def _check_digit(cls, value: str | None) -> str | None:
        if value is not None and not check_digit_ok(value):
            raise ValueError("gtin14 has a wrong check digit")
        return value

    @model_validator(mode="after")
    def _compare_at_not_below_price(self) -> OfferRow:
        if self.compare_at_cents is not None and self.compare_at_cents < self.price_cents:
            raise ValueError("compare_at_cents must be >= price_cents")
        return self

    @property
    def key(self) -> tuple[str, int]:
        return (self.retailer_id, self.variant_id)

    @property
    def available(self) -> bool:
        return self.availability == "in_stock"

    @property
    def discounted(self) -> bool:
        return self.compare_at_cents is not None and self.compare_at_cents > self.price_cents
