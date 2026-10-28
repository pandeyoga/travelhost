"""schemas_ops.py — skema master Add-on, pencairan fee driver & share-link jadwal (dipisah dari schemas.py, jaga <800 baris)."""
from typing import Annotated, List, Literal, Optional

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


class ScheduleShareVisibility(BaseModel):
    customer: bool = True
    driver: bool = True
    driver_phone: bool = False
    payment: bool = False
    notes: bool = False


class ScheduleShareCreate(BaseModel):
    """Share-link jadwal keberangkatan (read-only publik). Lihat services/schedule_share.py."""
    label: Optional[str] = Field(default="", max_length=120)
    scope: Literal["upcoming", "month", "range", "all"] = "upcoming"
    days: Optional[int] = Field(default=30, ge=0, le=366)  # upcoming: 0 = tanpa batas akhir
    month: Optional[str] = Field(default=None, max_length=7, pattern=r"^\d{4}-\d{2}$")
    start: Optional[str] = Field(default=None, max_length=10, pattern=r"^\d{4}-\d{2}-\d{2}$")
    end: Optional[str] = Field(default=None, max_length=10, pattern=r"^\d{4}-\d{2}-\d{2}$")
    vehicle_ids: List[Annotated[str, Field(max_length=64)]] = Field(default_factory=list, max_length=200)
    statuses: Optional[List[Literal["pending", "hold", "confirmed", "ongoing", "completed", "cancelled"]]] = Field(
        default=None, max_length=6)
    visibility: ScheduleShareVisibility = Field(default_factory=ScheduleShareVisibility)
    hours: Optional[int] = Field(default=720, ge=0, le=24 * 365)  # 0 = tanpa batas waktu


# === Phase 6: Maintenance + share-link tracking (dipindah dari schemas.py) ===
class MaintenanceCreate(BaseModel):
    vehicle_id: str = Field(min_length=1)
    type: Optional[str] = Field(default="servis", max_length=40)  # servis | kir | pajak | perbaikan | lainnya
    title: Optional[str] = Field(default="", max_length=200)
    description: Optional[str] = ""
    scheduled_date: Optional[str] = None
    start_date: Optional[str] = None  # window mulai (memblok availability)
    end_date: Optional[str] = None    # window selesai
    odometer: Optional[float] = Field(default=0, ge=0)
    cost: Optional[float] = Field(default=0, ge=0)
    workshop: Optional[str] = ""
    workshop_id: Optional[str] = None  # E8: ref ke koleksi workshops (master vendor/bengkel)
    status: Optional[str] = Field(default="scheduled", max_length=32)  # scheduled | in_progress | done | cancelled
    note: Optional[str] = Field(default="", max_length=1000)


class MaintenanceUpdate(BaseModel):
    type: Optional[str] = Field(default=None, max_length=40)
    title: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = None
    scheduled_date: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    odometer: Optional[float] = Field(default=None, ge=0)
    cost: Optional[float] = Field(default=None, ge=0)
    workshop: Optional[str] = None
    workshop_id: Optional[str] = None  # E8: ref ke koleksi workshops
    status: Optional[str] = Field(default=None, max_length=32)
    note: Optional[str] = Field(default=None, max_length=1000)


class MaintenanceComplete(BaseModel):
    completed_at: Optional[str] = None
    odometer: Optional[float] = Field(default=None, ge=0)
    cost: Optional[float] = Field(default=None, ge=0)
    note: Optional[str] = Field(default="", max_length=1000)


class ShareCreate(BaseModel):
    trip_id: str = Field(min_length=1)
    label: Optional[str] = Field(default="", max_length=120)
    hours: Optional[int] = Field(default=72, ge=0)  # masa berlaku tautan (jam)
