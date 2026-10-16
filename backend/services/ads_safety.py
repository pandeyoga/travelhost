"""services/ads_safety.py — PENGAMAN BELANJA IKLAN (satu-satunya pintu tulis ke platform).

Kenapa modul ini WAJIB dilewati: mulai fase F7 ERP boleh MEMBUAT kampanye/adset/iklan di Meta &
Google. Salah satu baris kode bisa membakar uang sungguhan. Pengaman di sini bersifat
*fail-closed* dan diletakkan di SATU tempat supaya bisa dijaga guardrail statik (INV-ADS-01):

  1. Mode `validate`  -> Meta `execution_options:["validate_only"]`, Google `validateOnly:true`.
     Tidak ada objek dibuat, tidak ada rupiah keluar.
  2. Mode `publish`   -> objek DIBUAT tapi status DIPAKSA `PAUSED` (tidak pernah langsung ACTIVE).
  3. Mengaktifkan (`ACTIVE`) atau menaikkan budget WAJIB menyertakan konfirmasi ketik nama objek.
  4. Budget harian dibatasi plafon dari Pengaturan (`max_daily_budget_minor`) — ditolak di ERP,
     bukan mengandalkan validasi platform.

Semua pelanggaran melempar `SafetyError` (dipetakan ke HTTP 400 oleh router, BUKAN 5xx).
"""

MODES = ("validate", "publish")
PAUSED = "PAUSED"
ACTIVE = "ACTIVE"
CREATE_KINDS = ("campaign", "adset", "ad")


class SafetyError(ValueError):
    """Permintaan tulis melanggar pengaman belanja — jangan pernah diteruskan ke platform."""


def normalize_mode(mode) -> str:
    m = str(mode or "validate").strip().lower()
    if m not in MODES:
        raise SafetyError(f"Mode tulis tidak dikenal: '{mode}'. Pilih 'validate' atau 'publish'.")
    return m


def is_dry_run(mode) -> bool:
    return normalize_mode(mode) == "validate"


def meta_write_payload(payload: dict, *, mode: str, kind: str) -> dict:
    """Bentuk body Meta yang aman. `kind`: campaign|adset|creative|ad|update."""
    body = dict(payload or {})
    if kind in CREATE_KINDS:
        body["status"] = PAUSED  # dipaksa, apa pun yang dikirim pemanggil
    if is_dry_run(mode):
        body["execution_options"] = ["validate_only"]
    else:
        body.pop("execution_options", None)
    return body


def google_write_body(body: dict, *, mode: str) -> dict:
    """Bentuk body Google Ads `:mutate` yang aman (validateOnly + partialFailure)."""
    out = dict(body or {})
    out["validateOnly"] = is_dry_run(mode)
    out.setdefault("partialFailure", True)
    return out


def google_force_paused(operations, *, kind: str):
    """Paksa status PAUSED pada operasi create Google (campaign/adGroup/adGroupAd)."""
    if kind not in CREATE_KINDS + ("adgroup", "adgroupad"):
        return operations
    out = []
    for op in operations or []:
        item = dict(op)
        if "create" in item:
            create = dict(item["create"])
            create["status"] = PAUSED
            item["create"] = create
        out.append(item)
    return out


def assert_confirmation(expected_name: str, typed: str) -> None:
    expected = (expected_name or "").strip()
    given = (typed or "").strip()
    if not expected:
        raise SafetyError("Nama objek untuk konfirmasi tidak diketahui — tindakan dibatalkan.")
    if given != expected:
        raise SafetyError(
            f"Konfirmasi tidak cocok. Ketik ulang persis nama objek: '{expected}'.")


def assert_budget_within_cap(amount_minor, cap_minor, *, currency: str = "") -> int:
    """Budget harian (satuan terkecil mata uang akun) wajib > 0 dan <= plafon ERP."""
    try:
        amount = int(amount_minor)
    except (TypeError, ValueError):
        raise SafetyError("Budget harian harus berupa angka bulat.") from None
    if amount <= 0:
        raise SafetyError("Budget harian harus lebih besar dari 0.")
    cap = int(cap_minor or 0)
    if cap > 0 and amount > cap:
        raise SafetyError(
            f"Budget harian {amount:,} {currency} melebihi plafon yang diizinkan "
            f"({cap:,} {currency}). Ubah plafon di Pengaturan → Integrasi bila memang perlu."
            .replace(",", "."))
    return amount


def assert_activation_allowed(status: str, *, expected_name: str, typed_name: str) -> str:
    """ACTIVE hanya boleh lewat konfirmasi ketik nama. PAUSED selalu boleh (mematikan itu aman)."""
    target = str(status or "").strip().upper()
    if target not in (ACTIVE, PAUSED):
        raise SafetyError(f"Status '{status}' tidak diizinkan. Pilih ACTIVE atau PAUSED.")
    if target == ACTIVE:
        assert_confirmation(expected_name, typed_name)
    return target


def summary(mode: str) -> dict:
    """Ringkasan untuk UI supaya user tahu persis apa yang akan terjadi."""
    dry = is_dry_run(mode)
    return {
        "mode": normalize_mode(mode),
        "dry_run": dry,
        "label": "Validasi saja (tidak membuat objek & tidak ada biaya)" if dry
                 else "Terbitkan objek dengan status DIJEDA (belum menghabiskan biaya)",
    }
