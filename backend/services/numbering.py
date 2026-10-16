"""services/numbering.py — penomoran dokumen terkonfigurasi (pola + token), meniru SIPRO.

Aturan per kunci disimpan di `numbering_rules` (override atas REGISTRY). Counter atomik
via services.counters.next_seq. Nomor yang sudah terbit tidak berubah — aturan hanya
berlaku untuk nomor berikutnya.
"""
import re
from datetime import datetime, timezone

from core_utils import now_iso
from services.counters import next_seq

ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
_TOKEN_RE = re.compile(r"\{([A-Z_]+)(?::(\d+))?\}")
EDITABLE = ("pattern", "prefix", "width", "reset", "start")

GLOBAL_TOKENS = [
    ("PREFIX", "Awalan aturan (kolom Awalan)", "INV"),
    ("SEQ", "Nomor urut; {SEQ:6} memaksa 6 digit", "0001"),
    ("SEQ_ALPHA", "Nomor urut huruf: A, B, … Z, AA", "A"),
    ("YYYY", "Tahun 4 digit", "2026"),
    ("YY", "Tahun 2 digit", "26"),
    ("MM", "Bulan 2 digit", "06"),
    ("MM_ROMAN", "Bulan romawi", "VI"),
    ("DD", "Tanggal 2 digit", "15"),
    ("YYMMDD", "Tanggal ringkas", "260615"),
    ("ORG_INITIALS", "Inisial nama perusahaan", "RT"),
]
CONTEXT_TOKENS = {
    "BOOKING_CODE": ("Kode booking", "BK-0012"),
    "CUSTOMER_INITIALS": ("Inisial nama pelanggan", "BS"),
    "DOC_CODE": ("Kode jenis dokumen", "DP"),
    "VEHICLE_CODE": ("Plat / kode armada", "D1234AB"),
}
RESET_OPTIONS = {"never": "Tidak pernah", "yearly": "Tahunan", "monthly": "Bulanan", "daily": "Harian"}
_CTX = list(CONTEXT_TOKENS)


def _r(key, label, prefix, doc_code, pattern="{PREFIX}-{YYYY}-{SEQ}", width=4, reset="yearly", desc=""):
    return {"key": key, "label": label, "prefix": prefix, "doc_code": doc_code, "pattern": pattern,
            "width": width, "reset": reset, "tokens": _CTX, "desc": desc, "group": "keuangan"}


REGISTRY = [
    _r("invoice", "Invoice penuh (tagihan total)", "INV", "INV", desc="Melanjutkan urutan INV-TAHUN-URUT yang lama."),
    _r("invoice_dp", "Invoice uang muka (DP)", "INV-DP", "DP"),
    _r("invoice_settlement", "Invoice pelunasan", "INV-PL", "PL"),
    _r("receipt", "Kwitansi penerimaan pembayaran", "KWT", "KWT"),
]
REGISTRY_BY_KEY = {r["key"]: r for r in REGISTRY}
GROUP_LABELS = {"keuangan": "Keuangan & Dokumen"}


def initials(name: str, n: int = 3) -> str:
    words = [w for w in re.split(r"[^A-Za-z0-9]+", name or "") if w]
    if len(words) == 1:
        return words[0][:n].upper()
    return "".join(w[0] for w in words[:n]).upper()


def seq_alpha(n: int) -> str:
    out = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


def tokens_in(pattern: str) -> list:
    return [m.group(1) for m in _TOKEN_RE.finditer(pattern or "")]


def validate_pattern(pattern: str) -> list:
    errs = []
    if not (pattern or "").strip():
        return ["Pola tidak boleh kosong."]
    known = {t for t, _, _ in GLOBAL_TOKENS} | set(CONTEXT_TOKENS)
    for t in tokens_in(pattern):
        if t not in known:
            errs.append(f"Token {{{t}}} tidak dikenal.")
    if re.search(r"\{[^}]*$|^[^{]*\}", pattern):
        errs.append("Kurung kurawal tidak seimbang.")
    if not any(t in ("SEQ", "SEQ_ALPHA") for t in tokens_in(pattern)):
        errs.append("Pola harus memuat {SEQ} atau {SEQ_ALPHA} agar nomor unik.")
    return errs


def _now():
    return datetime.now(timezone.utc)


def _period(reset: str, dt: datetime):
    if reset == "never":
        return None
    if reset == "monthly":
        return dt.strftime("%Y%m")
    if reset == "daily":
        return dt.strftime("%Y%m%d")
    return dt.strftime("%Y")


def _scope(key: str, period) -> str:
    return f"{key}:{period}" if period else key


def render(pattern: str, tokens: dict, n: int, width: int, dt: datetime) -> str:
    base = {"YYYY": dt.strftime("%Y"), "YY": dt.strftime("%y"), "MM": dt.strftime("%m"),
            "DD": dt.strftime("%d"), "YYMMDD": dt.strftime("%y%m%d"), "MM_ROMAN": ROMAN[dt.month]}

    def sub(m):
        tok, w = m.group(1), m.group(2)
        if tok == "SEQ":
            return str(n).zfill(int(w) if w else width)
        if tok == "SEQ_ALPHA":
            return seq_alpha(n)
        return str(tokens.get(tok, base.get(tok, "")))
    return _TOKEN_RE.sub(sub, pattern)


async def effective_rule(db, key: str) -> dict:
    base = REGISTRY_BY_KEY[key]
    ov = await db.numbering_rules.find_one({"key": key}, {"_id": 0}) or {}
    rule = {**base, **{k: ov[k] for k in EDITABLE if k in ov and ov[k] is not None}}
    rule["overridden"] = bool(ov)
    rule["updated_by"], rule["updated_at"] = ov.get("updated_by"), ov.get("updated_at")
    rule.setdefault("start", 1)
    return rule


async def _org_initials(db) -> str:
    doc = await db.settings.find_one({"key": "company_info"}, {"_id": 0}) or {}
    return initials((doc.get("value") or {}).get("name") or "Travel")


async def _peek(db, key: str, rule: dict) -> int:
    doc = await db.counters.find_one({"id": _scope(key, _period(rule["reset"], _now()))}, {"_id": 0})
    return max(int((doc or {}).get("seq") or 0) + 1, int(rule.get("start") or 1))


async def preview(db, rule: dict, sample: dict = None) -> str:
    samples = {t: ex for t, (_, ex) in CONTEXT_TOKENS.items()}
    samples["ORG_INITIALS"] = await _org_initials(db)
    samples["DOC_CODE"] = rule.get("doc_code") or samples["DOC_CODE"]
    samples.update({k.upper(): str(v) for k, v in (sample or {}).items() if v not in (None, "")})
    samples["PREFIX"] = rule.get("prefix") or ""
    n = await _peek(db, rule["key"], rule)
    return render(rule["pattern"], samples, n, int(rule["width"]), _now())


async def list_rules(db) -> list:
    out = []
    for r in REGISTRY:
        rule = await effective_rule(db, r["key"])
        rule["default"] = {k: r.get(k) for k in ("pattern", "prefix", "width", "reset")}
        rule["default"]["start"] = 1
        rule["group_label"] = GROUP_LABELS.get(r["group"], r["group"])
        rule["preview"] = await preview(db, rule)
        rule["next_seq"] = await _peek(db, r["key"], rule)
        out.append(rule)
    return out


async def save_rule(db, key: str, patch: dict, actor: str) -> dict:
    if key not in REGISTRY_BY_KEY:
        raise LookupError("Aturan penomoran tidak dikenal.")
    base = REGISTRY_BY_KEY[key]
    pattern = str(patch.get("pattern") or base["pattern"]).strip()
    errs = validate_pattern(pattern)
    if errs:
        raise ValueError(" ".join(errs))
    reset = patch.get("reset") or base["reset"]
    if reset not in RESET_OPTIONS:
        raise ValueError("Kebijakan reset tidak dikenal.")
    width = int(patch.get("width") or base["width"])
    start = int(patch.get("start") or 1)
    if not 1 <= width <= 8 or start < 1:
        raise ValueError("Lebar digit 1–8 dan nomor awal minimal 1.")
    doc = {"key": key, "pattern": pattern,
           "prefix": patch["prefix"] if patch.get("prefix") is not None else base["prefix"],
           "width": width, "reset": reset, "start": start, "updated_by": actor, "updated_at": now_iso()}
    await db.numbering_rules.update_one({"key": key}, {"$set": doc}, upsert=True)
    return await effective_rule(db, key)


async def reset_rule(db, key: str) -> dict:
    await db.numbering_rules.delete_one({"key": key})
    return await effective_rule(db, key)


async def generate(db, key: str, context: dict = None) -> str:
    """Nomor berikutnya untuk aturan `key` (counter naik)."""
    rule = await effective_rule(db, key)
    dt = _now()
    ctx = context or {}
    tokens = {
        "PREFIX": rule.get("prefix") or "",
        "BOOKING_CODE": str(ctx.get("booking_code") or "").upper(),
        "CUSTOMER_INITIALS": initials(ctx.get("customer_name") or "", 2),
        "DOC_CODE": rule.get("doc_code") or "",
        "VEHICLE_CODE": re.sub(r"[^A-Za-z0-9]", "", str(ctx.get("vehicle_code") or "")).upper(),
        "ORG_INITIALS": await _org_initials(db),
    }
    scope = _scope(key, _period(rule["reset"], dt))
    n = await next_seq(db, scope)
    start = int(rule.get("start") or 1)
    if n < start:
        await db.counters.update_one({"id": scope}, {"$set": {"seq": start}})
        n = start
    return render(rule["pattern"], tokens, n, int(rule["width"]), dt)


def token_catalog(key: str) -> list:
    rows = [{"token": t, "desc": d, "example": ex, "kind": "umum"} for t, d, ex in GLOBAL_TOKENS]
    rows += [{"token": t, "desc": d, "example": ex, "kind": "konteks"} for t, (d, ex) in CONTEXT_TOKENS.items()]
    return rows
