import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import {
  MapPin, Package, Newspaper, Quote, Tag, Plus, Pencil, Trash2, ShieldAlert, Palette,
  Copy, Eye, Search, ArrowUpDown, CheckCircle2, XCircle, ChevronDown, Star, TrendingUp,
  CalendarClock, Link2, Languages, History, ArrowLeftRight, EyeOff, Loader2,
  LayoutTemplate, Settings2,
} from "lucide-react";
import apiClient from "@/services/apiClient";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import ConfirmDialog from "@/components/shared/ConfirmDialog";
import ContentFormDialog from "@/components/app/ContentFormDialog";
import ReviewModerationPanel from "@/components/app/ReviewModerationPanel";
import ContentAnalyticsPanel from "@/components/app/ContentAnalyticsPanel";
import ThemeManagerPanel from "@/components/cms/ThemeManagerPanel";
import RedirectManagerPanel from "@/components/cms/RedirectManagerPanel";
import PageBuilderPanel from "@/components/cms/PageBuilderPanel";
import SiteSettingsPanel from "@/components/cms/SiteSettingsPanel";
import TrashDialog from "@/components/cms/TrashDialog";
import VersionHistoryDialog from "@/components/cms/VersionHistoryDialog";
import { formatCurrency, formatDateTime } from "@/utils/formatters";
import { SCHEMAS } from "@/features/app/contentSchemas";

// SSOT konfigurasi field per resource dipindah ke `contentSchemas.js`
// (menjaga file komponen < 500 baris sesuai guardrail arsitektur).
export { SCHEMAS };

const TABS = [
  ["destinations", "Destinasi", MapPin],
  ["packages", "Paket", Package],
  ["articles", "Artikel", Newspaper],
  ["testimonials", "Testimoni", Quote],
  ["promos", "Promo", Tag],
  ["reviews", "Ulasan", Star],
  ["analytics", "Analitik", TrendingUp],
  ["redirects", "Pengalihan", ArrowLeftRight],
  ["pages", "Halaman", LayoutTemplate],
  ["site", "Pengaturan Situs", Settings2],
  ["theme", "Tema Situs", Palette],
];

// Tab yang bukan daftar konten CRUD.
const PANEL_TABS = new Set(["reviews", "analytics", "redirects", "pages", "site", "theme"]);
// CMS-05: resource dengan siklus terbit (SSOT: services/content_publish.PUBLISHABLE).
const PUBLISHABLE = new Set(["destinations", "packages", "articles"]);
// CMS-06: resource yang punya field terjemahan (SSOT: services/i18n.TRANSLATABLE).
const TRANSLATABLE = new Set(["destinations", "packages", "articles", "promos"]);
const STATUS_FILTERS = [["all", "Semua status"], ["published", "Tayang"], ["scheduled", "Terjadwal"], ["draft", "Draft"]];
const LOCALE_FILTERS = [["all", "Semua bahasa"], ["en", "Sudah ada EN"], ["missing", "Belum ada EN"]];

// CMS-13: label aksi massal mengikuti kosakata tiap jenis konten — "Tayangkan" untuk halaman
// publik, "Setujui" untuk testimoni, "Aktifkan" untuk promo. Satu kata yang salah di sini
// membuat pemilik ragu menekan tombol massal.
const BULK_LABELS = {
  testimonials: { publish: "Setujui", unpublish: "Sembunyikan" },
  promos: { publish: "Aktifkan", unpublish: "Nonaktifkan" },
  _default: { publish: "Tayangkan", unpublish: "Jadikan draft" },
};

// Halaman Light CMS (B3 + G1-G10 + CMS-05..CMS-09) — kelola seluruh konten website dari satu tempat.
export default function ContentManager() {
  const [tab, setTab] = useState("destinations");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(null);
  const [denied, setDenied] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [editItem, setEditItem] = useState(null);
  const [delItem, setDelItem] = useState(null);
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");  // G5: search bar
  const [status, setStatus] = useState("all");  // CMS-05: filter status terbit
  const [locale, setLocale] = useState("all");  // CMS-06: filter ketersediaan terjemahan EN
  // CMS-10/11/13: riwayat versi, tempat sampah, dan seleksi untuk aksi massal.
  const [historyItem, setHistoryItem] = useState(null);
  const [trashOpen, setTrashOpen] = useState(false);
  const [selected, setSelected] = useState([]);          // array id (urutan = urutan klik)
  const [bulkBusy, setBulkBusy] = useState("");          // aksi yang sedang jalan
  const [bulkDelete, setBulkDelete] = useState(false);   // konfirmasi hapus massal
  // CMS-D3: paginasi (limit + offset + total via X-Total-Count header).
  const PAGE_SIZE = 50;
  const [total, setTotal] = useState(0);

  const schema = SCHEMAS[tab];
  const publishable = PUBLISHABLE.has(tab);
  const translatable = TRANSLATABLE.has(tab);

  const listParams = useCallback((offset) => {
    const qs = new URLSearchParams();
    if (query.trim()) qs.set("q", query.trim());
    if (publishable && status !== "all") qs.set("status", status);
    if (translatable && locale !== "all") qs.set("translated", locale);
    qs.set("limit", String(PAGE_SIZE));
    qs.set("offset", String(offset));
    return qs.toString();
  }, [query, status, locale, publishable, translatable]);

  // CMS-D3: reset ke halaman pertama; utk "Muat Lebih Banyak" gunakan loadMore().
  const load = useCallback(() => {
    if (PANEL_TABS.has(tab)) { setLoading(false); return; }
    setLoading(true);
    apiClient.get(`/content/${tab}?${listParams(0)}`)
      .then((r) => {
        const list = Array.isArray(r.data) ? r.data : [];
        setRows(list);
        // Seleksi massal dibersihkan dari id yang tak lagi tampil (mis. sesudah filter/hapus)
        // supaya tombol massal tidak pernah bekerja pada konten yang tidak dilihat pengguna.
        const visible = new Set(list.map((x) => x.id));
        setSelected((s) => s.filter((id) => visible.has(id)));
        const t = Number(r.headers?.["x-total-count"] ?? r.headers?.["X-Total-Count"] ?? 0);
        setTotal(Number.isFinite(t) ? t : 0);
        setError(null);
        setDenied(false);
      })
      .catch((e) => { if (e?.response?.status === 403) setDenied(true); else setError("Gagal memuat konten"); })
      .finally(() => setLoading(false));
  }, [tab, listParams]);

  const loadMore = useCallback(() => {
    if (loadingMore || rows.length >= total) return;
    setLoadingMore(true);
    apiClient.get(`/content/${tab}?${listParams(rows.length)}`)
      .then((r) => {
        const more = Array.isArray(r.data) ? r.data : [];
        setRows((prev) => [...prev, ...more]);
        const t = Number(r.headers?.["x-total-count"] ?? r.headers?.["X-Total-Count"] ?? 0);
        if (Number.isFinite(t)) setTotal(t);
      })
      .catch(() => toast.error("Gagal memuat halaman berikutnya"))
      .finally(() => setLoadingMore(false));
  }, [tab, listParams, rows.length, total, loadingMore]);

  // Debounce search: reload 350ms setelah user berhenti mengetik.
  useEffect(() => {
    const t = setTimeout(() => load(), 350);
    return () => clearTimeout(t);
  }, [load]);

  const onAdd = () => { setEditItem(null); setFormOpen(true); };
  const onEdit = (item) => { setEditItem(item); setFormOpen(true); };

  // CMS-11: hapus tidak lagi permanen — tawarkan pembatalan LANGSUNG di toast supaya
  // editor tidak perlu tahu di mana Tempat Sampah berada untuk membatalkan salah klik.
  const undoDelete = async (trashId, label) => {
    try {
      await apiClient.post(`/content/trash/${trashId}/restore`);
      toast.success(`"${label}" dipulihkan sebagai draft`);
      load();
    } catch (e) {
      const detail = e?.response?.data?.detail || "Gagal memulihkan";
      toast.error(detail, {
        duration: 10000,
        action: { label: "Buka Tempat Sampah", onClick: () => setTrashOpen(true) },
      });
    }
  };

  const confirmDelete = async () => {
    if (!delItem) return;
    setBusy(true);
    try {
      const label = schema.title(delItem) || delItem.id;
      const { data } = await apiClient.delete(`/content/${tab}/${delItem.id}`);
      const trashId = data?.trash_id;
      toast.success(`"${label}" dipindahkan ke Tempat Sampah`, {
        duration: 12000,
        description: `Masih bisa dipulihkan ${data?.retention_days || 30} hari ke depan.`,
        action: trashId
          ? { label: "Batalkan", onClick: () => undoDelete(trashId, label) }
          : undefined,
      });
      setDelItem(null);
      setSelected((s) => s.filter((id) => id !== delItem.id));
      load();
    }
    catch { toast.error("Gagal menghapus"); }
    finally { setBusy(false); }
  };

  // CMS-13: satu aksi untuk banyak konten. Kegagalan per-item DILAPORKAN (bukan disembunyikan).
  const runBulk = async (action) => {
    if (!selected.length) return;
    setBulkBusy(action);
    try {
      const { data } = await apiClient.post(`/content/${tab}/bulk`,
        { action, ids: selected });
      const failed = data?.failed || [];
      const verb = action === "delete" ? "dipindahkan ke Tempat Sampah"
        : action === "publish" ? "ditayangkan/disetujui" : "disembunyikan";
      if (data?.done) toast.success(`${data.done} konten ${verb}`);
      if (failed.length) {
        toast.error(`${failed.length} konten gagal: ${failed.map((f) => f.reason).slice(0, 2).join("; ")}`,
          { duration: 10000 });
      }
      setSelected([]);
      setBulkDelete(false);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Aksi massal gagal");
    } finally { setBulkBusy(""); }
  };

  const toggleSelect = (id) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  const allSelected = rows.length > 0 && selected.length === rows.length;
  const toggleSelectAll = () => setSelected(allSelected ? [] : rows.map((r) => r.id));
  const bulkLabels = BULK_LABELS[tab] || BULK_LABELS._default;

  // G8: duplicate konten
  const onDuplicate = async (item) => {
    try {
      const { data } = await apiClient.post(`/content/${tab}/${item.id}/duplicate`);
      toast.success(`Duplikat dibuat: ${schema.title(data) || data.id} (status draft)`);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menduplikasi"); }
  };

  // G7 + A1: buka halaman publik konten (route yang benar-benar ada di App.js).
  const onPreview = (item) => {
    if (!schema.publicPath) return;
    const slug = item[schema.publicSlugField];
    if (!slug) { toast.message("Item belum punya slug — simpan dulu"); return; }
    window.open(`${schema.publicPath}${slug}`, "_blank", "noopener");
  };

  // CMS-05: tautan pratinjau bertoken untuk konten yang BELUM tayang.
  const onPreviewToken = async (item) => {
    try {
      const { data } = await apiClient.post(`/content/${tab}/${item.id}/preview-token`);
      const href = /^https?:/i.test(String(data.url || ""))
        ? data.url
        : `${window.location.origin}${String(data.url || "").startsWith("/") ? "" : "/"}${data.url}`;
      try { await navigator.clipboard.writeText(href); } catch { /* izin clipboard ditolak */ }
      toast.success("Tautan pratinjau (24 jam) disalin — dibuka di tab baru");
      window.open(href, "_blank", "noopener");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal membuat tautan pratinjau");
    }
  };

  // Reorder via manual position input di list (inline update `position` field)
  const [editPosId, setEditPosId] = useState(null);
  const [editPosVal, setEditPosVal] = useState("");
  const savePosition = async (item) => {
    const p = Number(editPosVal);
    if (Number.isNaN(p)) { setEditPosId(null); return; }
    try {
      await apiClient.put(`/content/${tab}/${item.id}`, { position: p });
      toast.success("Urutan diperbarui"); setEditPosId(null); load();
    } catch { toast.error("Gagal menyimpan urutan"); }
  };

  const addBtn = (
    <button className="primary-button" onClick={onAdd} data-testid="content-add"><Plus size={14} /> Tambah {schema?.label}</button>
  );

  const statusPill = (it) => {
    // CMS-05: resource dengan siklus terbit memakai `effective_status` (terjadwal yang
    // waktunya sudah lewat = sudah tayang) supaya badge tidak pernah berbohong.
    if (publishable) {
      const eff = it.effective_status || it.status || "draft";
      if (eff === "published") return { label: "Tayang", tone: "tone-success" };
      if (eff === "scheduled") return { label: "Terjadwal", tone: "tone-warning" };
      return { label: "Draft", tone: "tone-neutral" };
    }
    if ("approved" in it) return { label: it.approved ? "Disetujui" : "Menunggu", tone: it.approved ? "tone-success" : "tone-warning" };
    if ("active" in it) return { label: it.active ? "Aktif" : "Nonaktif", tone: it.active ? "tone-success" : "tone-neutral" };
    return null;
  };

  /** Baris kedua: info yang berbeda per jenis konten (jadwal, kuota promo, harga, terjemahan). */
  const subLine = (it) => {
    const parts = [schema.sub(it)];
    if (typeof it.price_from === "number" && it.price_from) parts.push(`mulai ${formatCurrency(it.price_from)}`);
    if (typeof it.discount_value === "number" && it.discount_value) {
      parts.push(it.discount_type === "percent" ? `${it.discount_value}%` : formatCurrency(it.discount_value));
    }
    if (tab === "promos") {
      const max = Number(it.max_uses || 0);
      const used = Number(it.used_count || 0);
      parts.push(max > 0 ? `kuota ${used}/${max}` : `dipakai ${used}×`);
    }
    if (publishable && (it.effective_status || it.status) === "scheduled" && it.publish_at) {
      parts.push(`terbit ${formatDateTime(it.publish_at)}`);
    }
    return parts.filter(Boolean).join(" · ");
  };

  const hasEnTranslation = (it) => Boolean((it.translations || {}).en && Object.keys(it.translations.en).length);

  if (denied) {
    return (
      <div className="flex flex-col items-center rounded-[14px] border border-[#FFE0DC] bg-[#FFF5F4] px-6 py-16 text-center" data-testid="content-denied">
        <ShieldAlert size={28} className="mb-3 text-[#FF3B30]" />
        <h3 className="text-base font-bold text-[#1C1C1E]">Akses terbatas</h3>
        <p className="mt-1 max-w-sm text-sm text-[#6B6B73]">Konten Web hanya dapat dikelola oleh Pemilik & Admin Operasional.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="content-page">
      <div className="tab-bar">
        {TABS.map(([k, l, Icon]) => (
          <button key={k} className={`tab-button ${tab === k ? "active" : ""}`} onClick={() => { setTab(k); setQuery(""); setStatus("all"); setLocale("all"); setSelected([]); }} data-testid={`content-tab-${k}`}>
            <Icon size={14} /> {l}
          </button>
        ))}
      </div>

      {tab === "theme" ? <ThemeManagerPanel />
        : tab === "reviews" ? <ReviewModerationPanel />
        : tab === "analytics" ? <ContentAnalyticsPanel />
        : tab === "redirects" ? <RedirectManagerPanel />
        : tab === "pages" ? <PageBuilderPanel />
        : tab === "site" ? <SiteSettingsPanel />
        : (<>
      {/* G5: search bar + filter status (CMS-05) + Tambah + info total (CMS-D3) */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-1 flex-wrap items-center gap-2">
          <div className="relative w-full max-w-sm">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#8A8A8F]" />
            <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={`Cari ${schema.label.toLowerCase()}…`} className="pl-8" data-testid="content-search" />
          </div>
          {publishable ? (
            <Select value={status} onValueChange={setStatus}>
              <SelectTrigger className="h-9 w-[150px]" data-testid="content-status-filter"><SelectValue /></SelectTrigger>
              <SelectContent>
                {STATUS_FILTERS.map(([v, l]) => (
                  <SelectItem key={v} value={v} data-testid={`content-status-opt-${v}`}>{l}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : null}
          {translatable ? (
            <Select value={locale} onValueChange={setLocale}>
              <SelectTrigger className="h-9 w-[160px]" data-testid="content-locale-filter"><SelectValue /></SelectTrigger>
              <SelectContent>
                {LOCALE_FILTERS.map(([v, l]) => (
                  <SelectItem key={v} value={v} data-testid={`content-locale-opt-${v}`}>{l}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : null}
          {!loading && total > 0 ? (
            <span className="text-[12px] text-[#6B6B73] tabular-nums" data-testid="content-count">
              Menampilkan <span className="font-semibold text-[#1C1C1E]">{rows.length}</span> dari <span className="font-semibold text-[#1C1C1E]">{total}</span>
            </span>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* CMS-11: jalan pulang dari salah hapus, terlihat langsung di halaman CMS. */}
          <button className="secondary-button" onClick={() => setTrashOpen(true)} data-testid="content-trash-open">
            <Trash2 size={14} /> Tempat Sampah
          </button>
          {addBtn}
        </div>
      </div>

      {/* CMS-13: bar aksi massal — hanya muncul saat ada yang dipilih (tidak menambah derau). */}
      {selected.length > 0 ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-[12px] border border-[#CFE0FF] bg-[#F2F7FF] px-3 py-2"
          data-testid="content-bulk-bar">
          <p className="text-[12.5px] font-semibold text-[#0058CC] tabular-nums" data-testid="content-bulk-count">
            {selected.length} dipilih
          </p>
          <div className="flex flex-wrap items-center gap-1.5">
            <button className="secondary-button !h-8 !px-2.5 !text-[11.5px]" disabled={Boolean(bulkBusy)}
              onClick={() => runBulk("publish")} data-testid="content-bulk-publish">
              {bulkBusy === "publish" ? <Loader2 size={12} className="animate-spin" /> : <CheckCircle2 size={12} />} {bulkLabels.publish}
            </button>
            <button className="secondary-button !h-8 !px-2.5 !text-[11.5px]" disabled={Boolean(bulkBusy)}
              onClick={() => runBulk("unpublish")} data-testid="content-bulk-unpublish">
              {bulkBusy === "unpublish" ? <Loader2 size={12} className="animate-spin" /> : <EyeOff size={12} />} {bulkLabels.unpublish}
            </button>
            <button className="secondary-button !h-8 !px-2.5 !text-[11.5px] !text-[#A8221A]" disabled={Boolean(bulkBusy)}
              onClick={() => setBulkDelete(true)} data-testid="content-bulk-delete">
              <Trash2 size={12} /> Hapus
            </button>
            <button className="icon-button !h-8 !w-8" title="Bersihkan pilihan"
              onClick={() => setSelected([])} data-testid="content-bulk-clear"><XCircle size={13} /></button>
          </div>
        </div>
      ) : null}

      {loading ? <LoadingState testId="content-loading" />
        : error ? <ErrorState message={error} onRetry={load} />
        : rows.length === 0 ? <EmptyState title={query ? `Tidak ada hasil untuk "${query}"` : locale === "missing" ? `Semua ${schema.label.toLowerCase()} sudah punya versi English` : locale === "en" ? `Belum ada ${schema.label.toLowerCase()} dengan versi English` : status !== "all" ? `Tidak ada ${schema.label.toLowerCase()} berstatus ${status}` : `Belum ada ${schema.label.toLowerCase()}`} description={query || status !== "all" || locale !== "all" ? "Ubah kata kunci / filter status / filter bahasa, atau tekan Tambah." : "Tambahkan konten untuk ditampilkan di website."} testId="content-empty" action={addBtn} />
        : (
          <section className="section-card">
            {/* CMS-13: pilih semua yang sedang tampil (bukan seluruh database — hanya yang
                benar-benar dilihat pengguna, supaya aksi massal tidak pernah mengejutkan). */}
            <div className="flex items-center gap-2 border-b border-[#F2F2F5] px-4 py-2">
              <input type="checkbox" checked={allSelected} onChange={toggleSelectAll}
                aria-label="Pilih semua yang tampil"
                className="h-3.5 w-3.5 cursor-pointer accent-[#0058CC]" data-testid="content-select-all" />
              <span className="text-[11.5px] text-[#6B6B73]">
                {allSelected ? "Semua yang tampil dipilih" : "Pilih semua yang tampil"}
              </span>
            </div>
            <div className="divide-y divide-[#F2F2F5]" data-testid="content-list">
              {rows.map((it) => {
                const pill = statusPill(it);
                const eff = it.effective_status || it.status;
                const picked = selected.includes(it.id);
                return (
                <div key={it.id} className={`flex flex-wrap items-center justify-between gap-3 px-4 py-3 ${picked ? "bg-[#F7FAFF]" : ""}`} data-testid={`content-item-${it.id}`}>
                  <div className="flex min-w-0 flex-1 items-start gap-3">
                    <input type="checkbox" checked={picked} onChange={() => toggleSelect(it.id)}
                      aria-label={`Pilih ${schema.title(it) || it.id}`}
                      className="mt-1 h-3.5 w-3.5 flex-shrink-0 cursor-pointer accent-[#0058CC]"
                      data-testid={`content-select-${it.id}`} />
                    <div className="min-w-0 flex-1">
                    <p className="flex flex-wrap items-center gap-2 text-[13px] font-bold text-[#1C1C1E]">
                      {schema.title(it) || "(tanpa judul)"}
                      {pill ? <span className={`status-pill ${pill.tone}`}>{pill.tone === "tone-success" ? <CheckCircle2 size={10} /> : pill.tone === "tone-warning" ? <CalendarClock size={10} /> : <XCircle size={10} />} {pill.label}</span> : null}
                      {hasEnTranslation(it) ? <span className="status-pill tone-info" title="Punya versi English"><Languages size={10} /> EN</span> : null}
                      {typeof it.position === "number" && it.position !== 0 ? <span className="rounded bg-[#F2F2F5] px-1.5 py-0.5 text-[10px] font-semibold text-[#6B6B73]">#{it.position}</span> : null}
                    </p>
                    <p className="truncate text-[11.5px] tabular-nums text-[#6B6B73]">{subLine(it)}</p>
                    </div>
                  </div>
                  <div className="flex flex-shrink-0 items-center gap-1">
                    {/* Inline edit position (G10) */}
                    {editPosId === it.id ? (
                      <div className="flex items-center gap-1">
                        <Input type="number" value={editPosVal} onChange={(e) => setEditPosVal(e.target.value)} className="h-8 w-16" data-testid={`content-pos-input-${it.id}`} />
                        <button className="icon-button !h-8 !w-8 !text-[#34C759]" onClick={() => savePosition(it)} title="Simpan urutan" data-testid={`content-pos-save-${it.id}`}><CheckCircle2 size={14} /></button>
                        <button className="icon-button !h-8 !w-8" onClick={() => setEditPosId(null)} title="Batal"><XCircle size={14} /></button>
                      </div>
                    ) : (
                      <button className="icon-button !h-8 !w-8" title="Urutan tampil" onClick={() => { setEditPosId(it.id); setEditPosVal(String(it.position ?? "")); }} data-testid={`content-pos-${it.id}`}><ArrowUpDown size={13} /></button>
                    )}
                    {/* CMS-05: konten belum tayang dipratinjau lewat TOKEN (tanpa menayangkan). */}
                    {publishable && eff !== "published" ? (
                      <button className="icon-button !h-8 !w-8 !text-[#8A5A00]" title="Tautan pratinjau (24 jam)" onClick={() => onPreviewToken(it)} data-testid={`content-preview-token-${it.id}`}><Link2 size={13} /></button>
                    ) : null}
                    {schema.publicPath ? (
                      <button className="icon-button !h-8 !w-8" title="Buka halaman publik" onClick={() => onPreview(it)} data-testid={`content-preview-${it.id}`}><Eye size={13} /></button>
                    ) : null}
                    {/* CMS-10: riwayat versi + pulihkan isi lama. */}
                    <button className="icon-button !h-8 !w-8" title="Riwayat versi" onClick={() => setHistoryItem(it)} data-testid={`content-history-${it.id}`}><History size={13} /></button>
                    <button className="icon-button !h-8 !w-8" title="Duplikat" onClick={() => onDuplicate(it)} data-testid={`content-duplicate-${it.id}`}><Copy size={13} /></button>
                    <button className="icon-button !h-8 !w-8" title="Edit" onClick={() => onEdit(it)} data-testid={`content-edit-${it.id}`}><Pencil size={13} /></button>
                    <button className="icon-button !h-8 !w-8 !text-[#A8221A]" title="Hapus (masuk Tempat Sampah)" onClick={() => setDelItem(it)} data-testid={`content-delete-${it.id}`}><Trash2 size={13} /></button>
                  </div>
                </div>
              );})}
            </div>
            {/* CMS-D3: tombol Muat Lebih Banyak — muncul bila masih ada data */}
            {rows.length < total ? (
              <div className="flex items-center justify-center border-t border-[#F2F2F5] py-3">
                <button
                  className="secondary-button"
                  onClick={loadMore}
                  disabled={loadingMore}
                  data-testid="content-load-more"
                >
                  {loadingMore ? "Memuat…" : (<><ChevronDown size={14} /> Muat lebih banyak ({total - rows.length} tersisa)</>)}
                </button>
              </div>
            ) : null}
          </section>
        )}

      <ContentFormDialog resource={tab} schema={schema} item={editItem} open={formOpen} onOpenChange={setFormOpen} onSaved={load} />
      <ConfirmDialog open={Boolean(delItem)} onOpenChange={(v) => !v && setDelItem(null)} busy={busy}
        title={`Hapus ${schema?.label?.toLowerCase()}?`}
        description={`Konten dipindahkan ke Tempat Sampah dan masih bisa dipulihkan selama 30 hari — bukan dihapus permanen.`}
        onConfirm={confirmDelete} testId="content-confirm-delete" />
      {/* CMS-13: konfirmasi terpisah untuk hapus massal (jumlahnya disebut agar tidak salah klik). */}
      <ConfirmDialog open={bulkDelete} onOpenChange={(v) => !v && setBulkDelete(false)} busy={Boolean(bulkBusy)}
        title={`Hapus ${selected.length} ${schema?.label?.toLowerCase()}?`}
        description="Semuanya dipindahkan ke Tempat Sampah (retensi 30 hari) dan bisa dipulihkan satu per satu."
        confirmLabel={`Hapus ${selected.length} item`}
        onConfirm={() => runBulk("delete")} testId="content-confirm-bulk-delete" />
      {/* CMS-10 & CMS-11 */}
      <VersionHistoryDialog resource={tab} item={historyItem} open={Boolean(historyItem)}
        onOpenChange={(v) => !v && setHistoryItem(null)} onRestored={load} />
      <TrashDialog open={trashOpen} onOpenChange={setTrashOpen} resource={tab} onChanged={load} />
      </>)}
    </div>
  );
}
