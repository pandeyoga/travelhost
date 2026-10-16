"""schemas_landing.py — kontrak input API Landing Page Builder (FASE F8).

Dipisah dari `schemas.py` bukan karena estetika: `schemas.py` sudah menyentuh batas 800 baris
(dijaga `scripts/validate_compliance.py`) dan schema halaman iklan akan terus tumbuh seiring
blok baru. File terpisah membuat kontrak publik halaman iklan mudah ditinjau tanpa menggulir
seluruh ERP. Guardrail INV-NUM-01 memindai SEMUA `backend/schemas*.py`, jadi pemisahan ini
tidak mengurangi perlindungan batas nilai numerik.
"""
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class LandingLeadCreate(BaseModel):
    """Form lead di halaman iklan publik `/lp/{slug}`.

    Sengaja TOLERAN pada tipe (pax bisa datang sebagai teks dari input HTML) supaya pengunjung
    iklan tidak pernah melihat error teknis 422 hanya karena browser mengirim string kosong —
    setiap klik yang gagal di halaman iklan adalah uang iklan yang hangus.
    """
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=3, max_length=32)
    email: Optional[str] = Field(default="", max_length=160)
    origin: Optional[str] = Field(default="", max_length=160)
    destination: Optional[str] = Field(default="", max_length=160)
    start: Optional[str] = ""
    end: Optional[str] = ""
    pax: Optional[int] = Field(default=0, ge=0, le=500)
    vehicle_type: Optional[str] = ""
    message: Optional[str] = Field(default="", max_length=4000)
    hp: Optional[str] = ""            # honeypot anti-spam (harus kosong utk manusia)
    marketing_consent: Optional[bool] = False
    attribution: Optional[dict] = None   # {first_touch, last_touch, landing_page, referrer}
    click_ids: Optional[dict] = None     # {gclid, fbclid, ttclid, ctwa_clid, wbraid, gbraid}
    variant_id: Optional[str] = ""       # varian uji A/B yang dilihat pengunjung
    block_id: Optional[str] = ""
    idempotency_key: Optional[str] = ""

    @field_validator("pax", mode="before")
    @classmethod
    def _coerce_pax(cls, v):
        if v in (None, ""):
            return 0
        try:
            return max(0, min(500, int(float(v))))
        except (TypeError, ValueError):
            return 0


class LandingTrackEvent(BaseModel):
    """Peristiwa ringan halaman iklan untuk statistik A/B (tanpa PII)."""
    type: str = Field(default="view", max_length=40)  # view | cta_click
    variant_id: Optional[str] = "A"
    label: Optional[str] = Field(default="", max_length=120)
