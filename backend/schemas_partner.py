"""Skema Pinjam Armada / Sub-charter (E16 Partner Sourcing) — dipisah dari schemas.py
agar schemas.py tetap di bawah batas 800 baris (validate_compliance CHECK 1)."""
from typing import Optional
from pydantic import BaseModel, Field


# === E16: Pinjam Armada / Sub-charter (Partner Sourcing) ===
class PartnerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    pic: Optional[str] = ""
    phone: Optional[str] = Field(default="", max_length=24)
    email: Optional[str] = Field(default="", max_length=160)
    city: Optional[str] = Field(default="", max_length=80)
    address: Optional[str] = Field(default="", max_length=300)
    rating: Optional[float] = Field(default=0, ge=0)
    notes: Optional[str] = Field(default="", max_length=2000)
    status: Optional[str] = Field(default="active", max_length=32)


class PartnerUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    pic: Optional[str] = None
    phone: Optional[str] = Field(default=None, max_length=24)
    email: Optional[str] = Field(default=None, max_length=160)
    city: Optional[str] = Field(default=None, max_length=80)
    address: Optional[str] = Field(default=None, max_length=300)
    rating: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[str] = Field(default=None, max_length=32)


class SubcharterCreate(BaseModel):
    booking_id: str = Field(min_length=1)
    partner_id: str = Field(min_length=1)
    vehicle_id: Optional[str] = None
    vehicle_label: Optional[str] = ""
    start_datetime: Optional[str] = None
    end_datetime: Optional[str] = None
    cost: float = Field(gt=0)
    note: Optional[str] = Field(default="", max_length=1000)


class SubcharterUpdate(BaseModel):
    vehicle_id: Optional[str] = None
    vehicle_label: Optional[str] = None
    start_datetime: Optional[str] = None
    end_datetime: Optional[str] = None
    cost: Optional[float] = Field(default=None, ge=0)
    note: Optional[str] = Field(default=None, max_length=1000)


class SettlementCreate(BaseModel):
    amount: float = Field(gt=0)
    subcharter_id: Optional[str] = None
    method: Optional[str] = "transfer"
    note: Optional[str] = Field(default="", max_length=1000)
    paid_at: Optional[str] = None
