"""schemas_site.py — Page Builder situs publik + Pengaturan Situs (dipisah dari schemas.py
agar tetap di bawah batas baris). Konten teks disimpan sebagai OVERRIDE: kosong = pakai
teks bawaan dua-bahasa di frontend, terisi = tampil utk semua bahasa."""
from typing import List, Optional

from pydantic import BaseModel, Field


class SectionIn(BaseModel):
    id: Optional[str] = Field(default=None, max_length=60)
    type: str = Field(min_length=2, max_length=40)
    enabled: bool = True
    data: Optional[dict] = None


class SitePageUpdate(BaseModel):
    sections: List[SectionIn] = Field(max_length=20)


class SiteSettingsIn(BaseModel):
    """Merge (tambal) ke settings.company_info — satu sumber dgn header/footer/kontak publik."""
    name: Optional[str] = Field(default=None, max_length=120)
    tagline: Optional[str] = Field(default=None, max_length=300)
    logo_url: Optional[str] = Field(default=None, max_length=500)
    phone: Optional[str] = Field(default=None, max_length=40)
    whatsapp: Optional[str] = Field(default=None, max_length=24)
    email: Optional[str] = Field(default=None, max_length=160)
    address: Optional[str] = Field(default=None, max_length=300)
    city: Optional[str] = Field(default=None, max_length=80)
    service_area: Optional[str] = Field(default=None, max_length=120)
    work_hours_label: Optional[str] = Field(default=None, max_length=120)
    footer_text: Optional[str] = Field(default=None, max_length=500)
    instagram: Optional[str] = Field(default=None, max_length=300)
    facebook: Optional[str] = Field(default=None, max_length=300)
    tiktok: Optional[str] = Field(default=None, max_length=300)
    youtube: Optional[str] = Field(default=None, max_length=300)
    # Fitur situs: tampilkan/sembunyikan kalkulator estimasi trip (beranda, armada, menu, CTA).
    show_trip_calculator: Optional[bool] = None
    # URL situs publik (mis. https://rahazatrans.com) — dipakai pratinjau Page Builder
    # + tombol "buka di tab baru" saat ERP dilayani dari domain/subdomain terpisah.
    site_url: Optional[str] = Field(default=None, max_length=300)
