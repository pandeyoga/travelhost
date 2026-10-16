import { useCallback, useEffect, useMemo, useState } from "react";
import { Save, Rocket, ArrowUp, ArrowDown, EyeOff, Eye, Images, Copy, Monitor, Smartphone,
  ExternalLink, Loader2, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { LoadingState, ErrorState } from "@/components/shared/DataStates";
import SelectField from "@/components/shared/SelectField";
import LandingRender from "@/components/app/landing/LandingRender";
import LandingBlockForm, { BLOCK_LABELS } from "@/components/app/landing/LandingBlockForm";
import LandingAbPanel from "@/components/app/landing/LandingAbPanel";
import LandingPagesHome from "@/components/app/landing/LandingPagesHome";
import MediaLibrary from "@/components/app/landing/MediaLibrary";
import { AdReadinessPanel, PageLeadsPanel, SeoPanel, ThemePanel }
  from "@/components/app/landing/LandingSidePanels";

/**
 * LandingBuilder.jsx — editor halaman iklan (owner + marketing_admin).
 *
 * Dua SEGMEN iklan sesuai cara bisnis ini beriklan: **armada** (orang cari unit) dan
 * **destinasi** (orang cari pengalaman). Template menyiapkan struktur yang sudah terbukti,
 * lalu semua teks, tombol, dan warna bisa diubah di sini. Pratinjau memakai renderer yang
 * SAMA dengan halaman publik — tidak ada kejutan setelah terbit.
 *
 * Dua pengaman yang disengaja:
 *  1. **Penanda perubahan belum tersimpan.** Editor blok mengubah state lokal; tanpa penanda,
 *     mudah menekan "Terbitkan" dan menayangkan versi lama tanpa sadar.
 *  2. **Alasan belum layak terbit selalu terlihat** (INV-LP-01) sehingga tombol Terbitkan tidak
 *     pernah menolak tanpa penjelasan.
 */
const SEGMENTS = [{ value: "armada", label: "Segmen: Armada" }, { value: "destinasi", label: "Segmen: Destinasi" }];
const BLOCK_OPTIONS = Object.entries(BLOCK_LABELS).map(([value, label]) => ({ value, label }));

export default function LandingBuilder() {
  const [pages, setPages] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [presets, setPresets] = useState({});
  const [refs, setRefs] = useState({ fleet: [], destinations: [], routes: [], testimonials: [] });
  const [filters, setFilters] = useState({ q: "", segment: "", status: "" });
  const [active, setActive] = useState(null);
  const [dirty, setDirty] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState("");
  const [listLoading, setListLoading] = useState(false);
  const [selected, setSelected] = useState(0);
  const [device, setDevice] = useState("desktop");
  const [mediaOpen, setMediaOpen] = useState(false);
  const [leads, setLeads] = useState([]);
  const [leadsLoading, setLeadsLoading] = useState(false);
  const [readiness, setReadiness] = useState(null);
  const [readinessLoading, setReadinessLoading] = useState(false);

  const loadPages = useCallback(() => {
    const params = new URLSearchParams();
    if (filters.segment) params.set("segment", filters.segment);
    if (filters.status) params.set("status", filters.status);
    if (filters.q.trim()) params.set("q", filters.q.trim());
    return apiClient.get(`/landing/pages?${params.toString()}`).then((r) => setPages(r.data.pages || []));
  }, [filters]);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      apiClient.get("/landing/templates").then((r) => r.data),
      apiClient.get("/public/fleet").then((r) => r.data).catch(() => []),
      apiClient.get("/public/destinations").then((r) => r.data).catch(() => []),
      apiClient.get("/public/booking/config").then((r) => r.data).catch(() => ({})),
      apiClient.get("/public/testimonials").then((r) => r.data).catch(() => []),
      loadPages(),
    ]).then(([t, fleet, dest, cfg, testi]) => {
      setTemplates(t.templates || []);
      setPresets(t.theme_presets || {});
      const arr = (v) => (Array.isArray(v) ? v : v?.items || []);
      setRefs({ fleet: arr(fleet), destinations: arr(dest),
        routes: Array.isArray(cfg?.routes) ? cfg.routes : [], testimonials: arr(testi) });
      setError(null);
    }).catch((e) => setError(e?.response?.data?.detail || "Gagal memuat Landing Page Builder"))
      .finally(() => setLoading(false));
  }, [loadPages]);
  useEffect(load, [load]);

  useEffect(() => {
    if (loading || active) return;
    setListLoading(true);
    loadPages().catch(() => {}).finally(() => setListLoading(false));
  }, [filters, loading, active, loadPages]);

  // Peringatkan bila menutup tab dengan perubahan belum tersimpan.
  useEffect(() => {
    if (!dirty) return undefined;
    const warn = (e) => { e.preventDefault(); e.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const loadLeads = (id) => {
    setLeadsLoading(true);
    apiClient.get(`/landing/pages/${id}/leads`).then((r) => setLeads(r.data.leads || []))
      .catch(() => setLeads([])).finally(() => setLeadsLoading(false));
  };

  const loadReadiness = (id) => {
    setReadinessLoading(true);
    apiClient.get(`/landing/pages/${id}/readiness`).then((r) => setReadiness(r.data))
      .catch(() => setReadiness(null)).finally(() => setReadinessLoading(false));
  };

  const open = async (id) => {
    try {
      const { data } = await apiClient.get(`/landing/pages/${id}`);
      setActive(data);
      setSelected(0);
      setDirty(false);
      loadLeads(id);
      loadReadiness(id);
    } catch (e) {
      toast.error("Gagal membuka halaman");
    }
  };

  const create = async (template) => {
    setBusy("create");
    try {
      const { data } = await apiClient.post("/landing/pages", { template });
      toast.success("Halaman dibuat dari template — silakan ubah teks & warnanya");
      await open(data.id);
      await loadPages();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal membuat halaman");
    } finally {
      setBusy("");
    }
  };

  const save = async () => {
    if (!active) return null;
    setBusy("save");
    try {
      const { data } = await apiClient.patch(`/landing/pages/${active.id}`, {
        title: active.title, slug: active.slug, segment: active.segment, theme: active.theme,
        seo: active.seo, tracking: active.tracking, blocks: active.blocks, ab: active.ab,
      });
      setActive((a) => ({ ...a, ...data.page, publish_errors: data.publish_errors }));
      setDirty(false);
      (data.warnings || []).forEach((w) => toast.warning(w));
      toast.success("Perubahan disimpan");
      loadReadiness(active.id);
      return data;
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan");
      return null;
    } finally {
      setBusy("");
    }
  };

  const publish = async (unpublish = false) => {
    if (dirty && !unpublish) {
      const saved = await save();
      if (!saved) return;
    }
    setBusy("publish");
    try {
      const { data } = await apiClient.post(`/landing/pages/${active.id}/publish`, { unpublish });
      setActive((a) => ({ ...a, status: data.status, publish_errors: [] }));
      toast.success(unpublish ? "Halaman ditarik dari publikasi" : `Terbit! Alamat halaman: ${data.url}`);
      await loadPages();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengubah status terbit");
    } finally {
      setBusy("");
    }
  };

  const duplicate = async (id) => {
    setBusy("duplicate");
    try {
      const { data } = await apiClient.post(`/landing/pages/${id}/duplicate`, {});
      toast.success(`Duplikat dibuat sebagai draf: /lp/${data.slug}`);
      await loadPages();
      if (active?.id === id) await open(data.id);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menduplikat halaman");
    } finally {
      setBusy("");
    }
  };

  const remove = async (page) => {
    if (!window.confirm(`Hapus halaman “${page.title}”? Statistiknya ikut terhapus.`)) return;
    try {
      await apiClient.delete(`/landing/pages/${page.id}`);
      setPages((ps) => ps.filter((p) => p.id !== page.id));
      if (active?.id === page.id) setActive(null);
      toast.success("Halaman dihapus");
    } catch (e) {
      toast.error("Gagal menghapus halaman");
    }
  };

  const patchActive = (fn) => { setActive((a) => fn(a)); setDirty(true); };
  const setBlocks = (fn) => patchActive((a) => ({ ...a, blocks: fn(a.blocks || []) }));
  const moveBlock = (i, dir) => setBlocks((bs) => {
    const n = [...bs];
    const j = i + dir;
    if (j < 0 || j >= n.length) return n;
    [n[i], n[j]] = [n[j], n[i]];
    setSelected(j);
    return n;
  });
  const addBlock = (type) => {
    setBlocks((bs) => [...bs, { id: `blk_new_${Date.now()}`, type, hidden: false, device: "all", props: {} }]);
    setSelected((active?.blocks || []).length);
    toast.info(`Blok “${BLOCK_LABELS[type] || type}” ditambahkan di bawah — isi lalu Simpan`);
  };

  const previewWidth = useMemo(() => (device === "mobile" ? 420 : "100%"), [device]);

  if (loading) return <LoadingState testId="lp-loading" />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  if (!active) {
    return (
      <>
        <LandingPagesHome pages={pages} templates={templates} filters={filters} onFilter={setFilters}
          busy={busy} loading={listLoading} onCreate={create} onOpen={open} onDuplicate={duplicate}
          onDelete={remove} onOpenMedia={() => setMediaOpen(true)} />
        <MediaLibrary open={mediaOpen} onOpenChange={setMediaOpen} />
      </>
    );
  }

  const blocks = active.blocks || [];
  const block = blocks[selected];
  const errors = active.publish_errors || [];

  return (
    <div className="space-y-3" data-testid="landing-editor">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" className="secondary-button" data-testid="lp-back"
            onClick={() => {
              if (dirty && !window.confirm("Ada perubahan belum tersimpan. Tinggalkan halaman ini?")) return;
              setActive(null);
              setDirty(false);
              loadPages();
            }}>← Daftar</button>
          <input value={active.title} data-testid="lp-title" aria-label="Judul halaman"
            onChange={(e) => patchActive((a) => ({ ...a, title: e.target.value }))}
            className="h-9 w-[220px] rounded-lg border border-[#E5E5EA] bg-white px-3 text-[13px] font-semibold outline-none focus:border-[#007AFF]" />
          <div className="flex h-9 items-center rounded-lg border border-[#E5E5EA] bg-white pl-2.5">
            <span className="text-[12px] text-[#8E8E93]">/lp/</span>
            <input value={active.slug} data-testid="lp-slug" aria-label="Slug halaman"
              onChange={(e) => patchActive((a) => ({ ...a, slug: e.target.value }))}
              className="h-full w-[150px] rounded-r-lg bg-transparent px-1 text-[12.5px] outline-none" />
          </div>
          <div className="w-[170px]">
            <SelectField value={active.segment} testId="lp-segment" className="w-full"
              onChange={(v) => patchActive((a) => ({ ...a, segment: v }))} options={SEGMENTS} />
          </div>
          {dirty ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-[#FFF8EC] px-2.5 py-1 text-[11px] font-bold text-[#8A5300]"
              data-testid="lp-dirty">
              <AlertTriangle size={11} /> Belum tersimpan
            </span>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="secondary-button" onClick={() => setMediaOpen(true)} data-testid="lp-media-open">
            <Images size={14} /> Media
          </button>
          <button type="button" className="secondary-button" onClick={() => duplicate(active.id)}
            disabled={busy === "duplicate"} data-testid="lp-duplicate">
            <Copy size={14} /> Duplikat
          </button>
          {active.status === "published" ? (
            <a className="secondary-button" href={`/lp/${active.slug}`} target="_blank" rel="noreferrer"
              data-testid="lp-open-public"><ExternalLink size={14} /> Buka publik</a>
          ) : null}
          <button type="button" className="secondary-button" onClick={save} disabled={busy === "save"}
            data-testid="lp-save">
            {busy === "save" ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            {busy === "save" ? "Menyimpan…" : "Simpan"}
          </button>
          {active.status === "published" ? (
            <button type="button" className="secondary-button" onClick={() => publish(true)}
              disabled={busy === "publish"} data-testid="lp-unpublish">
              <EyeOff size={14} /> Tarik dari Publik
            </button>
          ) : (
            <button type="button" className="primary-button" onClick={() => publish(false)}
              disabled={busy === "publish"} data-testid="lp-publish">
              {busy === "publish" ? <Loader2 size={14} className="animate-spin" /> : <Rocket size={14} />}
              {busy === "publish" ? "Menerbitkan…" : "Terbitkan"}
            </button>
          )}
        </div>
      </div>

      {errors.length ? (
        <div className="rounded-xl border border-[#FFD9A8] bg-[#FFF8EC] p-3 text-[12px] text-[#8A5300]"
          data-testid="lp-publish-errors">
          <b>Belum layak terbit:</b> {errors.join(" · ")}
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[230px_1fr_330px]">
        <section className="section-card !p-0">
          <div className="section-head"><h2 className="text-[13px]">Blok Halaman ({blocks.length})</h2></div>
          <div className="max-h-[560px] overflow-y-auto p-2" data-testid="lp-block-list">
            {blocks.map((b, i) => (
              <div key={b.id} className={`mb-1.5 flex items-center gap-1 rounded-lg border p-2 ${
                i === selected ? "border-[#007AFF] bg-[#F2F8FF]" : "border-[#EFF0F2] bg-white"}`}>
                <button type="button" onClick={() => setSelected(i)} data-testid={`lp-block-${i}`}
                  className="flex-1 truncate text-left text-[12px] font-semibold text-[#1C1C1E]">
                  {b.hidden ? <EyeOff size={10} className="mr-1 inline text-[#8E8E93]" /> : null}
                  {BLOCK_LABELS[b.type] || b.type}
                </button>
                <button type="button" className="icon-button !h-6 !w-6" onClick={() => moveBlock(i, -1)}
                  aria-label="Naikkan blok" data-testid={`lp-up-${i}`}><ArrowUp size={11} /></button>
                <button type="button" className="icon-button !h-6 !w-6" onClick={() => moveBlock(i, 1)}
                  aria-label="Turunkan blok" data-testid={`lp-down-${i}`}><ArrowDown size={11} /></button>
              </div>
            ))}
            {!blocks.length ? (
              <p className="px-1 py-3 text-[11.5px] text-[#8E8E93]" data-testid="lp-blocks-empty">
                Belum ada blok. Tambahkan dari daftar di bawah.
              </p>
            ) : null}
            <div className="mt-2 border-t border-[#EFF0F2] pt-2">
              <SelectField value="" onChange={(v) => v && addBlock(v)} testId="lp-add-block" className="w-full"
                placeholder="+ Tambah blok" options={BLOCK_OPTIONS} />
            </div>
          </div>
        </section>

        <section className="section-card !p-0 overflow-hidden">
          <div className="section-head flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-[13px]">Pratinjau (sama dengan halaman publik)</h2>
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-0.5 rounded-lg bg-[#F2F2F5] p-0.5">
                <button type="button" onClick={() => setDevice("desktop")} aria-label="Pratinjau desktop"
                  data-testid="lp-preview-desktop"
                  className={`rounded-md px-2 py-1 ${device === "desktop" ? "bg-white shadow-sm" : ""}`}>
                  <Monitor size={13} />
                </button>
                <button type="button" onClick={() => setDevice("mobile")} aria-label="Pratinjau ponsel"
                  data-testid="lp-preview-mobile"
                  className={`rounded-md px-2 py-1 ${device === "mobile" ? "bg-white shadow-sm" : ""}`}>
                  <Smartphone size={13} />
                </button>
              </div>
              <span className="text-[11px] text-[#8E8E93]">/lp/{active.slug}</span>
            </div>
          </div>
          <div className="max-h-[620px] overflow-y-auto bg-[#F2F2F5] p-2">
            <div className="mx-auto bg-white" style={{ width: previewWidth, maxWidth: "100%" }}>
              <LandingRender page={active} mode="preview" fleet={refs.fleet}
                destinations={refs.destinations} routes={refs.routes} testimonials={refs.testimonials}
                onCta={(cta) => toast.info(`Pratinjau: tombol “${cta?.label || "aksi"}” aktif di halaman publik`)}
                onSearch={() => toast.info("Pratinjau: pencarian aktif di halaman publik")} />
            </div>
          </div>
        </section>

        <div className="space-y-3">
          <LandingBlockForm block={block} fleet={refs.fleet} destinations={refs.destinations} routes={refs.routes}
            onChange={(next) => setBlocks((bs) => bs.map((b, i) => (i === selected ? next : b)))}
            onDelete={() => {
              setBlocks((bs) => bs.filter((_, i) => i !== selected));
              setSelected(0);
            }} />
          <ThemePanel theme={active.theme} presets={presets}
            onChange={(t) => patchActive((a) => ({ ...a, theme: t }))} />
          <SeoPanel seo={active.seo} tracking={active.tracking} slug={active.slug}
            onSeo={(s) => patchActive((a) => ({ ...a, seo: s }))}
            onTracking={(t) => patchActive((a) => ({ ...a, tracking: t }))} />
          <AdReadinessPanel report={readiness} loading={readinessLoading}
            onRefresh={() => loadReadiness(active.id)} onOpenMedia={() => setMediaOpen(true)}
            onUseForAds={() => {
              // Bawa pilihan halaman ke pembuat kampanye lewat URL agar tim tidak perlu
              // menyalin slug manual (sumber utama iklan yang mendarat di 404).
              const target = `/app/ads?tab=builder&lp=${encodeURIComponent(active.slug)}`;
              if (active.status !== "published") {
                toast.warning("Halaman masih draf — terbitkan dulu agar iklan tidak mendarat di 404");
              }
              window.location.assign(target);
            }} />
          <LandingAbPanel page={active} ab={active.ab} publicUrl={`/lp/${active.slug}`}
            onChange={(ab) => patchActive((a) => ({ ...a, ab }))} />
          <PageLeadsPanel leads={leads} loading={leadsLoading} />
        </div>
      </div>

      <MediaLibrary open={mediaOpen} onOpenChange={setMediaOpen} />
    </div>
  );
}
