"""Entities and value objects: Period, MetricRow, KpiRow, Decision, Anomaly."""

from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Platform = Literal["iOS", "Android"]  # platforms where the supposed apps are used


class Period(BaseModel):
    model_config = ConfigDict(frozen=True)
    start: date
    end: date

    @model_validator(mode="after")
    def _check_order(self) -> Self:
        if self.start > self.end:
            raise ValueError("start date must be before end date")
        return self

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


class MetricRow(BaseModel):
    model_config = ConfigDict(frozen=True)
    app_name: str
    platform: Platform
    country: str
    installs: int = Field(ge=0)
    in_app_revenue: float = Field(ge=0)
    ads_revenue: float = Field(ge=0)
    ua_cost: float = Field(ge=0)


class DatasetInfo(BaseModel):
    model_config = ConfigDict(frozen=True)
    table: str
    columns: dict[str, str]
    apps: list[str]
    platforms: list[str]
    countries: list[str]
    date_min: date
    date_max: date
    row_count: int
