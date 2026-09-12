import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Globe, ImagePlus, Images, Languages, Loader2, Save, Send, Upload } from "lucide-react";
import apiClient from "@/services/apiClient";
import MediaPickerDialog from "@/components/media/MediaPickerDialog";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import GalleryManager from "@/components/cms/GalleryManager";
import TourSceneBuilder from "@/components/cms/TourSceneBuilder";
import LivePreviewPanel from "@/components/cms/LivePreviewPanel";
import RichTextEditor from "@/components/cms/RichTextEditor";
import PublishControls from "@/components/cms/PublishControls";
import TranslationFields from "@/components/cms/TranslationFields";

const ARRAY_TYPES = new Set(["gallery", "tour", "multi"]);
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
// CMS-05: resource yang punya siklus terbit (draft/terjadwal/tayang) — SSOT-nya
// `backend/services/content_publish.PUBLISHABLE`.
const PUBLISHABLE = new Set(["destinations", "packages", "articles"]);

const STATUS_PILL = {
  draft: { label: "Draft", cls: "tone-neutral" },
  scheduled: { label: "Terjadwal", cls: "tone-warning" },
  published: { label: "Tayang", cls: "tone-success" },
};

const statusPillOf = (status) => STATUS_PILL[status] || STATUS_PILL.draft;

// Konversi dokumen API -> nilai form (array/json/bool/date dirapikan agar editable).
function toForm(fields, item) {
  const f = {};
  for (const fl of fields) {
    const v = item ? item[fl.k] : undefined;
    if (fl.type === "list") f[fl.k] = Array.isArray(v) ? v.join("\n") : (v || "");
    else if (fl.type === "tags") f[fl.k] = Array.isArray(v) ? v.join(", ") : (v || "");
    else if (fl.type === "json") f[fl.k] = v ? JSON.stringify(v, null, 2) : "";
    else if (fl.type === "bool") f[fl.k] = Boolean(v);
    else if (fl.type === "date") f[fl.k] = v ? String(v).slice(0, 10) : "";
    else if (fl.type === "multi") f[fl.k] = Array.isArray(v) ? v : [];
    else if (ARRAY_TYPES.has(fl.type)) f[fl.k] = Array.isArray(v) ? v : [];
    else f[fl.k] = v ?? "";
  }
  return f;
}

/** Nilai form (untuk tab English & pratinjau) dalam bentuk seperti dokumen API. */
function formToDoc(fields, form) {
  const out = {};
  for (const fl of fields) {
    const v = form[fl.k];
    if (fl.type === "list") out[fl.k] = String(v || "").split("\n").map((s) => s.trim()).filter(Boolean);
    else if (fl.type === "tags") out[fl.k] = String(v || "").split(",").map((s) => s.trim()).filter(Boolean);
    else out[fl.k] = v;
  }
  return out;
}

// Field image: pilih dari Media Library (unified) ATAU unggah berkas baru.
// Sebelumnya field ini HANYA punya tombol unggah ke `/api/uploads/cms` — artinya gambar yang sudah
// ada di sistem tidak bisa dipakai ulang, dan setiap pemakaian membuat berkas duplikat baru di disk.
// Sekarang tombol "Library" membuka pemilih yang sama dengan editor halaman iklan (folder, pencarian,
// potong gambar, ganti berkas), sementara tombol "Unggah" tetap ada untuk jalur tercepat.
function ImageField({ fieldKey, label, value, onChange, testId }) {
  const inputRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const openPicker = () => inputRef.current?.click();
  const onPick = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";  // reset agar file yg sama bisa dipilih ulang
    if (!file) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("image", file);
      const { data } = await apiClient.post("/uploads/cms", fd, { headers: { "Content-Type": "multipart/form-data" } });
      onChange(data.url);
      toast.success(`Terunggah (${Math.round(data.size_bytes / 1024)}KB) — tersimpan di Media Library`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Gagal mengunggah gambar");
    } finally { setBusy(false); }
  };
  // Preview URL: kalau relatif (/api/public/media/… atau /api/uploads/…) prefix dgn backend url.
  const previewSrc = value ? (String(value).startsWith("http") ? value : `${BACKEND_URL}${value}`) : "";
  return (
    <div className="space-y-1.5">
      <div className="flex gap-2">
        <Input value={value || ""} onChange={(e) => onChange(e.target.value)} placeholder="URL gambar, pilih dari Library, atau unggah" data-testid={testId} />
        <button type="button" onClick={() => setPickerOpen(true)} className="secondary-button !px-3 shrink-0" data-testid={`${testId}-library`}>
          <Images size={14} />
          <span className="hidden sm:inline">Library</span>
        </button>
        <button type="button" onClick={openPicker} disabled={busy} className="secondary-button !px-3 shrink-0" data-testid={`${testId}-upload`}>
          {busy ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
          <span className="hidden sm:inline">Unggah</span>
        </button>
        <input ref={inputRef} type="file" accept="image/jpeg,image/png,image/webp,image/gif" className="hidden" onChange={onPick} data-testid={`${testId}-file`} />
      </div>
      {previewSrc ? (
        <img src={previewSrc} alt="" className="h-24 w-full rounded-lg border border-border object-cover" loading="lazy" onError={(e) => { e.currentTarget.style.display = "none"; }} />
      ) : (
        <div className="flex h-24 w-full items-center justify-center rounded-lg border border-dashed border-[#E5E5EA] bg-[#F7F8FA] text-[11px] text-[#8A8A8F]">
          <ImagePlus size={16} className="mr-1.5" /> Belum ada gambar
        </div>
      )}
      <MediaPickerDialog open={pickerOpen} onOpenChange={setPickerOpen} pickKind="image"
        title={`Pilih gambar — ${label || fieldKey}`}
        onPick={(asset) => onChange(asset?.url || "")} />
    </div>
  );
}

/** Pilihan JAMAK (tipe armada / layanan promo). Kosong = berlaku untuk SEMUA (aturan server). */
function MultiField({ value, options, onChange, testId, allLabel = "Semua" }) {
  const list = Array.isArray(value) ? value : [];
  const toggle = (v) => onChange(list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  return (
    <div className="flex flex-wrap gap-1.5" data-testid={testId}>
      <button type="button" onClick={() => onChange([])}
        className={`rounded-full border px-2.5 py-1 text-[11.5px] font-semibold transition ${list.length === 0 ? "border-[#0058CC] bg-[#0058CC] text-white" : "border-[#E5E5EA] bg-white text-[#3A3A3C] hover:bg-[#F2F2F5]"}`}
        data-testid={`${testId}-all`}>{allLabel}</button>
      {(options || []).map((o) => {
        const active = list.includes(o.value);
        return (
          <button key={o.value} type="button" onClick={() => toggle(o.value)}
            className={`rounded-full border px-2.5 py-1 text-[11.5px] font-semibold transition ${active ? "border-[#0058CC] bg-[#E9F1FF] text-[#0058CC]" : "border-[#E5E5EA] bg-white text-[#3A3A3C] hover:bg-[#F2F2F5]"}`}
            data-testid={`${testId}-opt-${o.value}`}>{o.label}</button>
        );
      })}
    </div>
  );
}

// Dialog form generik CMS (B3 + P10/FASE 5 + G3/G4/G6 + CMS-05/06/09).
export default function ContentFormDialog({ resource, schema, item, open, onOpenChange, onSaved }) {
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [tab, setTab] = useState("id");
  // CMS-05 (status terbit) & CMS-06 (terjemahan) disimpan terpisah dari field biasa:
  // keduanya BUKAN field bebas — server punya aturan sendiri untuk keduanya.
  const [pub, setPub] = useState({ status: "draft", publish_at: "" });
  const [tr, setTr] = useState({});
  const [promoOptions, setPromoOptions] = useState({ vehicle_types: [], services: [] });
  const set = (k, v) => setForm((s) => ({ ...s, [k]: v }));

  const publishable = PUBLISHABLE.has(resource);

  useEffect(() => {
    if (!open) return;
    setForm(toForm(schema.fields, item));
    setTab("id");
    setPub({
      status: item?.status || (item?.id ? "published" : "draft"),
      publish_at: item?.publish_at || "",
    });
    setTr(((item?.translations || {}).en) || {});
  }, [open, item, schema]);

  // Opsi aturan promo diambil dari server (mesin harga + alur pemesanan) supaya
  // daftar tipe armada/layanan tidak pernah berbeda antara CMS dan checkout.
  useEffect(() => {
    if (!open || resource !== "promos") return;
    let alive = true;
    apiClient.get("/content/meta/promo-options")
      .then((r) => { if (alive) setPromoOptions(r.data || { vehicle_types: [], services: [] }); })
      .catch(() => { /* opsi kosong: field tetap bisa dikosongkan = berlaku semua */ });
    return () => { alive = false; };
  }, [open, resource]);

  const hasPreview = resource === "destinations" || resource === "articles";
  const seoFields = schema.fields.filter((f) => f.section === "seo");
  const mainFields = schema.fields.filter((f) => f.section !== "seo");

  const submit = async () => {
    const payload = {};
    for (const fl of schema.fields) {
      if (fl.type === "readonly") continue;
      const v = form[fl.k];
      if (fl.req && (v === "" || v === undefined || v === null)) { toast.message(`${fl.label} wajib diisi`); return; }
      if (fl.type === "list") payload[fl.k] = String(v || "").split("\n").map((s) => s.trim()).filter(Boolean);
      else if (fl.type === "tags") payload[fl.k] = String(v || "").split(",").map((s) => s.trim()).filter(Boolean);
      else if (fl.type === "json") {
        try { payload[fl.k] = v ? JSON.parse(v) : []; }
        catch { toast.error(`${fl.label}: format JSON tidak valid`); return; }
      } else if (fl.type === "number") payload[fl.k] = Number(v) || 0;
      else if (fl.type === "bool") payload[fl.k] = Boolean(v);
      else if (ARRAY_TYPES.has(fl.type)) payload[fl.k] = Array.isArray(v) ? v : [];
      else payload[fl.k] = v ?? "";
    }

    // CMS-05 — status terbit + jadwal.
    if (publishable) {
      if (pub.status === "scheduled" && !String(pub.publish_at || "").trim()) {
        setTab("publish");
        toast.error("Status Terjadwal wajib diisi tanggal & jam terbit");
        return;
      }
      payload.status = pub.status;
      payload.publish_at = pub.status === "scheduled" ? pub.publish_at : "";
    }

    // CMS-06 — kantong terjemahan (kosong = pakai versi Indonesia).
    const enClean = {};
    Object.entries(tr || {}).forEach(([k, v]) => {
      if (Array.isArray(v)) { if (v.length) enClean[k] = v; }
      else if (String(v || "").trim()) enClean[k] = v;
    });
    payload.translations = Object.keys(enClean).length ? { en: enClean } : {};

    setSaving(true);
    try {
      if (item?.id) await apiClient.put(`/content/${resource}/${item.id}`, payload);
      else await apiClient.post(`/content/${resource}`, payload);
      toast.success(item?.id ? "Konten diperbarui" : "Konten ditambahkan");
      onOpenChange(false); onSaved && onSaved();
    } catch (e) {
      const detail = e?.response?.data?.detail || "Gagal menyimpan";
      if (e?.response?.status === 409) toast.error(`Duplikat: ${detail}`);
      else toast.error(detail);
    }
    finally { setSaving(false); }
  };

  const renderField = (fl) => (
    <div key={fl.k} className="space-y-1">
      <Label className="text-[12px]">{fl.label}{fl.req ? " *" : ""}</Label>
      {fl.type === "richtext" ? (
        <RichTextEditor value={String(form[fl.k] || "")} onChange={(v) => set(fl.k, v)} testId={`cf-rte-${fl.k}`} />
      ) : fl.type === "readonly" ? (
        /* Field yang DIKELOLA SISTEM (mis. `used_count` promo). Dirender sebagai input
           `disabled` + `readOnly` — bukan sekadar teks — supaya jelas bagi pengguna DAN bagi
           alat uji bahwa field ini memang tidak bisa disunting manual. */
        <Input value={form[fl.k] === "" || form[fl.k] === undefined ? "0" : String(form[fl.k])}
          readOnly disabled aria-readonly="true" tabIndex={-1}
          className="!bg-[#F2F2F5] !text-[#3A3A3C] tabular-nums"
          data-testid={`cf-${fl.k}`} />
      ) : fl.type === "multi" ? (
        <MultiField value={form[fl.k]} options={promoOptions[fl.optionsKey] || []} allLabel={fl.allLabel}
          onChange={(v) => set(fl.k, v)} testId={`cf-${fl.k}`} />
      ) : fl.type === "textarea" || fl.type === "list" || fl.type === "json" ? (
        <Textarea rows={fl.type === "json" ? 4 : 3} value={form[fl.k] || ""} onChange={(e) => set(fl.k, e.target.value)} placeholder={fl.hint || ""} data-testid={`cf-${fl.k}`} />
      ) : fl.type === "bool" ? (
        <div className="pt-1"><Switch checked={Boolean(form[fl.k])} onCheckedChange={(v) => set(fl.k, v)} data-testid={`cf-${fl.k}`} /></div>
      ) : fl.type === "select" ? (
        <Select value={form[fl.k] || ""} onValueChange={(v) => set(fl.k, v)}>
          <SelectTrigger data-testid={`cf-${fl.k}`}><SelectValue placeholder="Pilih…" /></SelectTrigger>
          <SelectContent>{(fl.options || []).map(([v, l]) => <SelectItem key={v} value={v} data-testid={`cf-${fl.k}-opt-${v}`}>{l}</SelectItem>)}</SelectContent>
        </Select>
      ) : fl.type === "image" ? (
        <ImageField fieldKey={fl.k} label={fl.label} value={form[fl.k]} onChange={(v) => set(fl.k, v)} testId={`cf-${fl.k}`} />
      ) : fl.type === "gallery" ? (
        <GalleryManager value={form[fl.k] || []} onChange={(arr) => set(fl.k, arr)} mode={fl.galleryMode || "captioned"} />
      ) : fl.type === "tour" ? (
        <TourSceneBuilder value={form[fl.k] || []} onChange={(arr) => set(fl.k, arr)} />
      ) : (
        <Input type={fl.type === "number" ? "number" : fl.type === "date" ? "date" : "text"} value={form[fl.k] ?? ""} onChange={(e) => set(fl.k, e.target.value)} placeholder={fl.hint || ""} data-testid={`cf-${fl.k}`} />
      )}
      {fl.hint && (fl.type === "text" || fl.type === "textarea" || fl.type === "number" || fl.type === "multi" || fl.type === "readonly") ? (
        <p className="text-[10.5px] text-[#8A8A8F]">{fl.hint}</p>
      ) : null}
    </div>
  );

  const fieldsBlock = (
    <div className="space-y-3">
      {publishable ? (
        /* Pengingat status di tab Indonesia (kontrolnya SATU tempat: tab "Terbit"),
           supaya tidak ada dua pemilih status yang bisa berbeda isi. */
        <button type="button" onClick={() => setTab("publish")}
          className="flex w-full items-center justify-between gap-2 rounded-[12px] border border-[#E5E5EA] bg-[#F7F8FA] px-3 py-2 text-left"
          data-testid="cf-publish-hint">
          <span className="text-[11.5px] text-[#6B6B73]">
            Status terbit: <span className={`status-pill ${statusPillOf(pub.status).cls}`}>{statusPillOf(pub.status).label}</span>
            {pub.status === "scheduled" && pub.publish_at ? ` · ${String(pub.publish_at).replace("T", " ").slice(0, 16)} UTC` : ""}
          </span>
          <span className="text-[11.5px] font-semibold text-[#0058CC]">Atur di tab Terbit →</span>
        </button>
      ) : null}
      {mainFields.map(renderField)}
      {seoFields.length > 0 ? (
        <details className="rounded-lg border border-[#E5E5EA] bg-[#F7F8FA] px-3 py-2" open={Boolean(form.meta_title || form.meta_description || form.og_image)} data-testid="cf-seo-group">
          <summary className="cursor-pointer text-[12px] font-semibold text-[#1C1C1E]">SEO &amp; Sosial Media (opsional)</summary>
          <div className="mt-2 space-y-3">
            {seoFields.map(renderField)}
          </div>
        </details>
      ) : null}
    </div>
  );

  const enBlock = (
    <TranslationFields resource={resource} fields={schema.fields} base={formToDoc(schema.fields, form)}
      value={tr} onChange={setTr} />
  );

  const statusPill = statusPillOf(pub.status);
  const enCount = Object.values(tr || {}).filter((v) => (Array.isArray(v) ? v.length : String(v || "").trim())).length;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={`flex max-h-[92vh] flex-col overflow-hidden ${hasPreview ? "max-w-5xl" : "max-w-2xl"}`} data-testid="content-form-dialog">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            {item?.id ? "Edit" : "Tambah"} {schema.label}
            {publishable ? <span className={`status-pill ${statusPill.cls}`} data-testid="cf-status-pill">{statusPill.label}</span> : null}
          </DialogTitle>
        </DialogHeader>

        {/* CMS-06: satu konten, dua bahasa. Tab dipisah supaya editor tidak pernah bingung
            field mana yang dibaca pengunjung Indonesia dan mana yang dibaca turis asing. */}
        <div className="tab-bar" data-testid="cf-lang-tabs">
          <button type="button" className={`tab-button ${tab === "id" ? "active" : ""}`} onClick={() => setTab("id")} data-testid="cf-tab-id">
            <Globe size={13} /> Indonesia
          </button>
          <button type="button" className={`tab-button ${tab === "en" ? "active" : ""}`} onClick={() => setTab("en")} data-testid="cf-tab-en">
            <Languages size={13} /> English {enCount ? <span className="ml-1 rounded bg-[#E9F1FF] px-1 text-[10px] font-bold text-[#0058CC] tabular-nums">{enCount}</span> : null}
          </button>
          {publishable ? (
            <button type="button" className={`tab-button ${tab === "publish" ? "active" : ""}`} onClick={() => setTab("publish")} data-testid="cf-tab-publish">
              <Send size={13} /> Terbit
            </button>
          ) : null}
        </div>

        {tab === "en" ? (
          <div className="min-h-0 flex-1 overflow-y-auto">{enBlock}</div>
        ) : tab === "publish" ? (
          <div className="min-h-0 flex-1 space-y-3 overflow-y-auto">
            <PublishControls resource={resource} item={item} status={pub.status} publishAt={pub.publish_at}
              onChange={(patch) => setPub((s) => ({ ...s, ...patch }))} />
            <p className="rounded-[12px] border border-[#E5E5EA] bg-white px-3 py-2.5 text-[11.5px] leading-relaxed text-[#6B6B73]">
              <span className="font-semibold text-[#1C1C1E]">Draft</span> tidak pernah muncul di situs maupun sitemap.
              <span className="font-semibold text-[#1C1C1E]"> Terjadwal</span> terbit sendiri saat waktunya tiba (dicek penjadwal server tiap beberapa menit).
              <span className="font-semibold text-[#1C1C1E]"> Tayang</span> langsung terlihat pengunjung.
              Tautan pratinjau berlaku 24 jam dan hanya membuka konten ini.
            </p>
          </div>
        ) : hasPreview ? (
          <div className="grid min-h-0 flex-1 gap-4 overflow-y-auto lg:grid-cols-[1.45fr_1fr] lg:overflow-hidden">
            <div className="min-h-0 lg:overflow-y-auto lg:pr-2">{fieldsBlock}</div>
            <div className="min-h-0 lg:overflow-y-auto lg:border-l lg:border-border lg:pl-3">
              <LivePreviewPanel resource={resource} form={form} />
            </div>
          </div>
        ) : (
          <div className="min-h-0 flex-1 overflow-y-auto">{fieldsBlock}</div>
        )}

        <DialogFooter className="mt-2">
          <button className="secondary-button" onClick={() => onOpenChange(false)} data-testid="cf-cancel">Batal</button>
          <button className="primary-button" onClick={submit} disabled={saving} data-testid="cf-submit">{saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Simpan</button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
