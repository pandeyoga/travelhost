"""permissions_config.py — SSOT matrix RBAC (sinkron docs/05_NAVIGATION_MAP.md §3).

Role: owner, ops_admin, driver. Section = modul navigasi.
Dipakai oleh dependencies.require_role/require_section & dashboard.
"""

ROLES = ("owner", "ops_admin", "marketing_admin", "driver")

# Section -> himpunan role yang boleh mengakses (read minimal).
SECTION_ACCESS = {
    "dashboard": {"owner", "ops_admin", "marketing_admin", "driver"},
    "bookings": {"owner", "ops_admin", "driver"},
    # RBAC-CAL-01: "Kalender Keberangkatan" adalah permukaan MANAJEMEN (buat keberangkatan,
    # setujui/tolak permintaan publik, tugaskan sopir, ekspor jadwal armada) -> setara Dispatch,
    # jadi driver DILARANG (docs/05_NAVIGATION_MAP.md §3). Sebelumnya section ini tidak
    # dideklarasikan sama sekali sehingga endpoint kalender hanya ber-auth tanpa RBAC.
    "calendar": {"owner", "ops_admin"},
    # Ruang Kerja Driver: driver hanya melihat tugasnya sendiri (difilter di router driver.py).
    "driver-workspace": {"owner", "ops_admin", "driver"},
    "vehicles": {"owner", "ops_admin", "driver"},
    "drivers": {"owner", "ops_admin", "driver"},
    "customers": {"owner", "ops_admin", "marketing_admin"},
    "crm": {"owner", "ops_admin", "marketing_admin"},
    # Modul turunan CRM yang punya menu sendiri di FE (router-nya menegakkan require_section("crm")).
    # Dideklarasikan eksplisit agar matriks FE<->BE sinkron (dipaksa INV-RBAC-04).
    "quotations": {"owner", "ops_admin"},
    "inbox": {"owner", "ops_admin", "marketing_admin"},
    # --- FASE F (E29): modul Marketing & Iklan ---
    # 'ads'          : dashboard performa iklan (ops_admin boleh LIHAT; mutasi campaign dibatasi
    #                  require_role("owner","marketing_admin") di router).
    # 'landing'      : Landing Page Builder (advanced CMS) untuk halaman tujuan iklan.
    # 'tracking'     : Kesehatan Pelacakan (outbox konversi server-side).
    # 'integrations' : kredensial Meta/Google/WhatsApp (owner + marketing_admin saja).
    "ads": {"owner", "ops_admin", "marketing_admin"},
    "landing": {"owner", "marketing_admin"},
    "tracking": {"owner", "marketing_admin"},
    "integrations": {"owner", "marketing_admin"},
    "finance": {"owner", "ops_admin"},
    "reports": {"owner", "ops_admin"},
    "gps": {"owner", "ops_admin", "driver"},
    "maintenance": {"owner", "ops_admin", "driver"},
    "users": {"owner"},
    "settings": {"owner"},
    # Dokumen (invoice/kwitansi/penomoran/rekening): konfigurasi organisasi = owner saja.
    "documents": {"owner"},
    "audit": {"owner"},
    "sales": {"owner", "ops_admin"},
    "cms": {"owner", "ops_admin", "marketing_admin"},
    # --- Media Manager v2: SATU library media untuk CMS website + halaman iklan ---
    # Sengaja section TERSENDIRI (bukan menumpang 'landing'): 'landing' = {owner, marketing_admin}
    # karena halaman iklan berbayar tak boleh diubah peran yang tidak memegang anggaran iklan,
    # sementara 'ops_admin' WAJIB bisa mengelola foto destinasi/artikel/paket website. Menumpang
    # section landing berarti salah satu dari dua kebutuhan itu harus dikorbankan.
    # driver TIDAK termasuk: aset media adalah permukaan publikasi, bukan alat kerja sopir.
    "media": {"owner", "ops_admin", "marketing_admin"},
    "automation": {"owner", "ops_admin"},
    "dispatch": {"owner", "ops_admin"},
    "analytics": {"owner", "ops_admin"},
    "partners": {"owner", "ops_admin"},
    # Master Data referensi (titik jemput + destinasi ops) — halaman /app/masterdata.
    "masterdata": {"owner", "ops_admin"},
}


# Alias id-section frontend -> id kanonik backend (mencegah "drift SSOT" karena beda ejaan).
SECTION_ALIASES = {
    "auditlog": "audit",
}


def canonical_section(section: str) -> str:
    return SECTION_ALIASES.get(section, section)


def can_access(role: str, section: str) -> bool:
    return role in SECTION_ACCESS.get(canonical_section(section), set())


def allowed_sections(role: str):
    return [s for s, roles in SECTION_ACCESS.items() if role in roles]
