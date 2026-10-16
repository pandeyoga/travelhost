"""routers/documents.py — konfigurasi dokumen (tampilan, naskah, aset gambar), penomoran,
dan pengaturan invoice (DP/jatuh tempo/rekening). Baca = section finance; ubah = section settings.
"""
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field, field_validator

from core_utils import new_id, now_iso, safe_doc
from db import get_db
from dependencies import require_section
from services import doc_layout as dl
from services import doc_script as ds
from services import documents as docs
from services import numbering as nb
from services.audit import record

router = APIRouter(prefix="/api", tags=["documents"])
FIN = require_section("finance")
SET = require_section("settings")
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


class BrandIn(BaseModel):
    company_name: Optional[str] = None
    tagline: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    npwp: Optional[str] = None
    logo_file_id: Optional[str] = None
    header_image_file_id: Optional[str] = None
    footer_image_file_id: Optional[str] = None
    header_mode: Optional[str] = None
    footer_mode: Optional[str] = None
    accent_color: Optional[str] = None
    text_color: Optional[str] = None
    footer_text: Optional[str] = None
    show_page_numbers: Optional[bool] = None
    paper: Optional[str] = None
    margin_top_mm: Optional[float] = Field(default=None, ge=8, le=60)
    margin_bottom_mm: Optional[float] = Field(default=None, ge=8, le=60)
    margin_left_mm: Optional[float] = Field(default=None, ge=8, le=50)
    margin_right_mm: Optional[float] = Field(default=None, ge=8, le=50)
    watermark_text: Optional[str] = None
    watermark_file_id: Optional[str] = None
    watermark_opacity: Optional[int] = Field(default=None, ge=0, le=60)

    @field_validator("accent_color", "text_color")
    @classmethod
    def _color(cls, v):
        if v and not HEX.match(v):
            raise ValueError("Warna harus heksadesimal, mis. #007AFF.")
        return v

    @field_validator("header_mode", "footer_mode")
    @classmethod
    def _mode(cls, v):
        if v and v not in ("system", "image", "none"):
            raise ValueError("Mode kop/footer hanya: system, image, none.")
        return v

    @field_validator("paper")
    @classmethod
    def _paper(cls, v):
        if v and v not in ("A4", "LETTER", "LEGAL"):
            raise ValueError("Kertas hanya: A4, LETTER, LEGAL.")
        return v


class SectionIn(BaseModel):
    key: str
    label: Optional[str] = None
    visible: bool = True
    order: int = 0


class MoneyRowIn(BaseModel):
    code: str
    label: str = Field(min_length=1)
    visible: bool = True
    order: int = 0
    hide_if_zero: bool = True
    manual: bool = False
    amount: Optional[int] = None


class SignatureIn(BaseModel):
    title: str = Field(min_length=1)
    name: Optional[str] = None
    position: Optional[str] = None
    show_stamp: bool = False
    stamp_file_id: Optional[str] = None
    sign_file_id: Optional[str] = None
    auto_from_issuer: bool = False


class TableIn(BaseModel):
    grid: Optional[str] = None
    show_header: Optional[bool] = None
    header_fill: Optional[bool] = None
    zebra: Optional[bool] = None
    total_highlight: Optional[bool] = None
    font_size: Optional[float] = Field(default=None, ge=6, le=12)
    grid_color: Optional[str] = None
    width_pct: Optional[float] = Field(default=None, ge=40, le=100)
    alignment: Optional[str] = None


class OptionsIn(BaseModel):
    show_materai: Optional[bool] = None
    materai_note: Optional[str] = None
    show_place_date: Optional[bool] = None
    place: Optional[str] = None
    show_doc_number: Optional[bool] = None
    show_title: Optional[bool] = None
    hide_zero_rows: Optional[bool] = None
    closing_note: Optional[str] = None
    show_generated_note: Optional[bool] = None
    show_terbilang: Optional[bool] = None


class LayoutSave(BaseModel):
    brand: Optional[BrandIn] = None
    table: Optional[TableIn] = None
    sections: Optional[list[SectionIn]] = None
    money_rows: Optional[list[MoneyRowIn]] = None
    signatures: Optional[list[SignatureIn]] = Field(default=None, max_length=4)
    options: Optional[OptionsIn] = None


class PreviewIn(LayoutSave):
    script: Optional[str] = None


class ScriptSave(BaseModel):
    content: str = Field(max_length=20000)


class RuleSave(BaseModel):
    pattern: Optional[str] = None
    prefix: Optional[str] = None
    width: Optional[int] = Field(None, ge=1, le=8)
    reset: Optional[str] = None
    start: Optional[int] = Field(None, ge=1)


class PreviewRuleIn(RuleSave):
    sample: dict = {}


class BankAccount(BaseModel):
    id: Optional[str] = None
    bank: str = Field(min_length=1, max_length=60)
    account_no: str = Field(min_length=3, max_length=40)
    account_name: str = Field(min_length=1, max_length=120)


class InvoiceConfigIn(BaseModel):
    dp_percent_default: Optional[float] = Field(None, ge=0, le=100)
    dp_due_days: Optional[int] = Field(None, ge=0, le=90)
    settlement_due_days: Optional[int] = Field(None, ge=0, le=180)
    settlement_due_before_start_days: Optional[int] = Field(None, ge=0, le=60)
    bank_accounts: Optional[list[BankAccount]] = None
    payment_terms: Optional[str] = Field(None, max_length=3000)
    footer_note: Optional[str] = Field(None, max_length=500)


def _code(code: str) -> str:
    if code not in dl.TARGETS:
        raise HTTPException(status_code=404, detail=f"Dokumen '{code}' tidak dikenal.")
    return code


# ------------------------------------------------------------------ tampilan dokumen
@router.get("/doc-layouts")
async def list_layouts(user=Depends(FIN)):
    return {"data": await dl.list_targets(get_db()),
            "sections_catalog": [{"key": k, "label": lbl} for k, lbl in dl.SECTIONS],
            "money_rows_catalog": {k: [{"code": c, "label": lbl} for c, lbl in v] for k, v in dl.MONEY_ROWS.items()}}


@router.get("/doc-layouts/{code}")
async def get_layout(code: str, user=Depends(FIN)):
    return {"data": safe_doc(await dl.get_layout(get_db(), _code(code)))}


@router.put("/doc-layouts/{code}")
async def save_layout(code: str, body: LayoutSave, user=Depends(SET)):
    db = get_db()
    out = await dl.save_layout(db, _code(code), body.model_dump(exclude_none=True), user.get("email"))
    await record(db, actor=user, action="update", entity_type="document_layout", entity_id=code,
                 summary=f"Ubah tampilan dokumen {code}")
    return {"data": safe_doc(out)}


@router.delete("/doc-layouts/{code}")
async def reset_layout(code: str, user=Depends(SET)):
    db = get_db()
    out = await dl.reset_layout(db, _code(code))
    await record(db, actor=user, action="delete", entity_type="document_layout", entity_id=code,
                 summary=f"Reset tampilan dokumen {code} ke bawaan")
    return {"data": safe_doc(out)}


@router.get("/doc-layouts/{code}/script")
async def get_script(code: str, user=Depends(FIN)):
    return {"data": await ds.get_script(get_db(), _code(code))}


@router.put("/doc-layouts/{code}/script")
async def put_script(code: str, body: ScriptSave, user=Depends(SET)):
    db = get_db()
    try:
        out = await ds.save_script(db, _code(code), body.content, user.get("email"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await record(db, actor=user, action="update", entity_type="document_template", entity_id=code,
                 summary=f"Ubah naskah dokumen {code}")
    return {"data": out, "message": "Naskah dokumen disimpan."}


@router.delete("/doc-layouts/{code}/script")
async def reset_script(code: str, user=Depends(SET)):
    return {"data": await ds.reset_script(get_db(), _code(code))}


@router.post("/doc-layouts/{code}/preview")
async def preview_layout(code: str, body: PreviewIn, user=Depends(FIN)):
    """PDF pratinjau dari rancangan yang BELUM disimpan (data contoh, mesin cetak sama)."""
    db = get_db()
    rancangan = body.model_dump(exclude_none=True)
    script = rancangan.pop("script", None)
    layout = dl._merge(await dl.get_layout(db, _code(code)), rancangan)
    if script is not None:
        bad = ds.validate(code, script)
        if bad:
            raise HTTPException(status_code=400, detail="Placeholder tidak dikenal: " + ", ".join(bad))
    pdf = await docs.preview_pdf(db, code, layout, script, issuer=user)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="pratinjau-{code}.pdf"'})


# ------------------------------------------------------------------ aset gambar (logo/kop/ttd)
@router.post("/doc-assets")
async def upload_asset(file: UploadFile = File(...), user=Depends(SET)):
    ext = (Path(file.filename or "").suffix or "").lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        raise HTTPException(status_code=400, detail="Hanya gambar PNG/JPG/WEBP.")
    data = await file.read()
    if len(data) > 3 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Ukuran gambar maksimal 3 MB.")
    fid = new_id("dimg")
    folder = dl.UPLOAD_DIR / "docs"
    folder.mkdir(parents=True, exist_ok=True)
    fname = f"{fid}{ext}"
    (folder / fname).write_bytes(data)
    rec = {"id": fid, "filename": fname, "original": file.filename, "size": len(data),
           "url": f"/api/uploads/docs/{fname}", "uploaded_by": user.get("email"), "created_at": now_iso()}
    await get_db().doc_assets.insert_one(dict(rec))
    return safe_doc(rec)


@router.get("/doc-assets")
async def list_assets(user=Depends(FIN)):
    return safe_doc(await get_db().doc_assets.find({}, {"_id": 0}).sort("created_at", -1).to_list(200))


# ------------------------------------------------------------------ penomoran
@router.get("/numbering")
async def list_rules(user=Depends(FIN)):
    return {"data": await nb.list_rules(get_db()),
            "reset_options": [{"value": k, "label": v} for k, v in nb.RESET_OPTIONS.items()],
            "global_tokens": [{"token": t, "desc": d, "example": ex} for t, d, ex in nb.GLOBAL_TOKENS],
            "context_tokens": [{"token": t, "desc": d, "example": ex} for t, (d, ex) in nb.CONTEXT_TOKENS.items()]}


def _rule_key(key: str) -> str:
    if key not in nb.REGISTRY_BY_KEY:
        raise HTTPException(status_code=404, detail="Aturan penomoran tidak dikenal.")
    return key


@router.post("/numbering/{key}/preview")
async def preview_rule(key: str, body: PreviewRuleIn, user=Depends(FIN)):
    db = get_db()
    rule = await nb.effective_rule(db, _rule_key(key))
    patch = body.model_dump(exclude_none=True)
    sample = patch.pop("sample", {})
    rule.update({k: v for k, v in patch.items() if k in nb.EDITABLE})
    errs = nb.validate_pattern(rule["pattern"])
    if errs:
        raise HTTPException(status_code=400, detail=" ".join(errs))
    return {"data": {"preview": await nb.preview(db, rule, sample), "errors": []}}


@router.put("/numbering/{key}")
async def save_rule(key: str, body: RuleSave, user=Depends(SET)):
    db = get_db()
    try:
        out = await nb.save_rule(db, _rule_key(key), body.model_dump(exclude_none=True), user.get("email"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await record(db, actor=user, action="update", entity_type="numbering_rule", entity_id=key,
                 summary=f"Ubah aturan penomoran {key}: {out['pattern']}")
    out["preview"] = await nb.preview(db, out)
    return {"data": out, "message": "Aturan penomoran disimpan."}


@router.delete("/numbering/{key}")
async def reset_rule(key: str, user=Depends(SET)):
    db = get_db()
    out = await nb.reset_rule(db, _rule_key(key))
    out["preview"] = await nb.preview(db, out)
    return {"data": out, "message": "Aturan dikembalikan ke bawaan."}


# ------------------------------------------------------------------ pengaturan invoice
@router.get("/invoice-config")
async def get_invoice_config(user=Depends(FIN)):
    return await docs.invoice_config(get_db())


@router.put("/invoice-config")
async def put_invoice_config(body: InvoiceConfigIn, user=Depends(SET)):
    db = get_db()
    cur = await docs.invoice_config(db)
    patch = body.model_dump(exclude_none=True)
    if "bank_accounts" in patch:
        patch["bank_accounts"] = [{**a, "id": a.get("id") or new_id("bank")} for a in patch["bank_accounts"]]
    value = {**cur, **patch}
    await db.settings.update_one({"key": "invoice_config"}, {"$set": {"key": "invoice_config", "value": value}}, upsert=True)
    await record(db, actor=user, action="update", entity_type="settings", entity_id="invoice_config",
                 summary="Ubah pengaturan invoice (DP/jatuh tempo/rekening)")
    return value
