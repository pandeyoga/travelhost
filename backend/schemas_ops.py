"""schemas_ops.py — skema master Add-on & pencairan fee driver (dipisah dari schemas.py, jaga <800 baris)."""
from typing import Optional

from pydantic import BaseModel, Field


class AddonCreate(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    default_amount: float = Field(default=0, ge=0)
    active: Optional[bool] = True


class AddonUpdate(BaseModel):
    label: Optional[str] = Field(default=None, min_length=1, max_length=80)
    default_amount: Optional[float] = Field(default=None, ge=0)
    active: Optional[bool] = None


class WithdrawCreate(BaseModel):
    amount: float = Field(gt=0)
    bank_name: str = Field(min_length=1, max_length=60)
    account_number: str = Field(min_length=3, max_length=40)
    account_name: str = Field(min_length=1, max_length=80)
    note: Optional[str] = Field(default="", max_length=300)
    # Hanya dihormati untuk owner/ops_admin (buat pengajuan atas nama driver).
    driver_id: Optional[str] = Field(default=None, max_length=64)


class WithdrawReject(BaseModel):
    reason: str = Field(min_length=1, max_length=300)
