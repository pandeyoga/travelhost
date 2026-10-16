import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Plus, Save, ExternalLink, Loader2 } from "lucide-react";
import { DndContext, PointerSensor, closestCenter, useSensor, useSensors } from "@dnd-kit/core";
import { SortableContext, arrayMove, verticalListSortingStrategy } from "@dnd-kit/sortable";
import apiClient from "@/services/apiClient";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { LoadingState, ErrorState } from "@/components/shared/DataStates";
import { PAGES, PAGE_URL, SECTION_META } from "@/lib/siteSections";
import SectionCard from "@/components/cms/PageBuilderSectionCard";
import PageBuilderPreview from "@/components/cms/PageBuilderPreview";

// Page Builder: editor split-screen — kiri daftar section (drag & drop, edit isi,
// gambar dari Media Library), kanan pratinjau LANGSUNG halaman asli (draft tampil
// sebelum disimpan; klik section di pratinjau utk memilihnya di editor).

export default function PageBuilderPanel() {
  const [slug, setSlug] = useState("home");
  const [sections, setSections] = useState([]);
  const [allowed, setAllowed] = useState([]);
  const [addType, setAddType] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [base, setBase] = useState(window.location.origin);
  const cardRefs = useRef({});
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));

  const load = useCallback(async (s) => {
    setLoading(true); setError(null); setDirty(false); setSelectedId(null);
    try {
      const { data } = await apiClient.get(`/site/pages/${s}`);
      setSections(Array.isArray(data.sections) ? data.sections : []);
      setAllowed(Array.isArray(data.allowed_types) ? data.allowed_types : []);
    } catch (e) { setError(e?.response?.data?.detail || "Gagal memuat halaman"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(slug); }, [slug, load]);
  // URL situs publik (Pengaturan Situs / env PUBLIC_SITE_URL): pratinjau harus memuat SITUS
  // PUBLIK, bukan ERP — penting saat ERP dilayani dari subdomain terpisah ("/" → /app/login).
  useEffect(() => {
    apiClient.get("/site/settings").then((r) => {
      const u = String(r.data?.site_url || "").trim();
      if (u) { try { setBase(new URL(u).origin); } catch { /* abaikan URL tidak valid */ } }
    }).catch(() => {});
  }, []);

  const patch = (fn) => { setSections(fn); setDirty(true); };
  const move = (idx, dir) => patch((rows) => arrayMove(rows, idx, idx + dir));
  const onDragEnd = ({ active, over }) => {
    if (!over || active.id === over.id) return;
    patch((rows) => arrayMove(rows,
      rows.findIndex((r) => r.id === active.id), rows.findIndex((r) => r.id === over.id)));
  };
  const selectFromPreview = useCallback((id) => {
    setSelectedId(id);
    const el = cardRefs.current[id];
    if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await apiClient.put(`/site/pages/${slug}`, { sections });
      toast.success("Halaman disimpan — perubahan langsung tampil di situs");
      setDirty(false);
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menyimpan"); }
    finally { setSaving(false); }
  };

  return (
    <div className="space-y-3" data-testid="page-builder-panel">
      <div className="flex flex-wrap items-center gap-2">
        <div className="w-[200px]">
          <Select value={slug} onValueChange={setSlug}>
            <SelectTrigger data-testid="pb-page-select"><SelectValue /></SelectTrigger>
            <SelectContent>
              {PAGES.map((p) => <SelectItem key={p.slug} value={p.slug} data-testid={`pb-page-opt-${p.slug}`}>{p.label}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <a href={`${base}${PAGE_URL[slug]}`} target="_blank" rel="noreferrer" className="secondary-button !h-9 !px-3 !text-[12px]" data-testid="pb-preview">
          <ExternalLink size={12} /> Buka di tab baru
        </a>
        <div className="flex-1" />
        <button className="primary-button !h-9 !px-4 !text-[12.5px]" disabled={saving || !dirty} onClick={save} data-testid="pb-save">
          {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />} Simpan Halaman
        </button>
      </div>
      <p className="text-[12px] text-[#6B6B73]">
        Seret kartu utk mengubah urutan, klik section di PRATINJAU kanan utk memilihnya, dan setiap
        ketikan langsung tampil di pratinjau — situs asli baru berubah setelah "Simpan Halaman".
        Field kosong tetap memakai teks bawaan situs (dua bahasa).
      </p>
      <div className="flex flex-col gap-4 xl:flex-row">
        <div className="w-full xl:w-[440px] xl:shrink-0">
          {loading ? <LoadingState testId="pb-loading" /> : error ? <ErrorState message={error} onRetry={() => load(slug)} /> : (
            <>
              <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
                <SortableContext items={sections.map((s) => s.id)} strategy={verticalListSortingStrategy}>
                  <div className="space-y-2 xl:max-h-[calc(100vh-320px)] xl:overflow-y-auto xl:pr-1">
                    {sections.length === 0 ? (
                      <p className="rounded-xl border border-dashed border-[#D8D8DE] px-4 py-8 text-center text-[12.5px] text-[#8E8E93]" data-testid="pb-empty">Belum ada section — tambahkan dari daftar di bawah.</p>
                    ) : sections.map((sec, idx) => (
                      <SectionCard key={sec.id} sec={sec} idx={idx} total={sections.length}
                        selected={selectedId === sec.id}
                        registerRef={(el) => { cardRefs.current[sec.id] = el; }}
                        onSelect={() => setSelectedId(sec.id)}
                        onMove={move}
                        onToggle={(en) => patch((rows) => rows.map((r) => (r.id === sec.id ? { ...r, enabled: en } : r)))}
                        onChangeData={(data) => patch((rows) => rows.map((r) => (r.id === sec.id ? { ...r, data } : r)))}
                        onDelete={() => patch((rows) => rows.filter((r) => r.id !== sec.id))} />
                    ))}
                  </div>
                </SortableContext>
              </DndContext>
              <div className="mt-2 flex flex-wrap items-center gap-2 rounded-xl border border-[#E9E9EE] bg-[#FAFAFC] px-3.5 py-3">
                <span className="text-[12px] font-semibold text-[#6B6B73]">Tambah section:</span>
                <div className="w-[220px]">
                  <Select value={addType} onValueChange={setAddType}>
                    <SelectTrigger className="!h-8 bg-white text-[12px]" data-testid="pb-add-type"><SelectValue placeholder="Pilih tipe section…" /></SelectTrigger>
                    <SelectContent>
                      {allowed.map((t) => <SelectItem key={t} value={t} data-testid={`pb-add-opt-${t}`}>{(SECTION_META[t] || {}).label || t}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <button className="secondary-button !h-8 !px-3 !text-[11.5px]" disabled={!addType}
                  onClick={() => { patch((rows) => [...rows, { id: `new-${Date.now()}`, type: addType, enabled: true, data: {} }]); setAddType(""); }}
                  data-testid="pb-add-btn"><Plus size={12} /> Tambahkan</button>
              </div>
            </>
          )}
        </div>
        <PageBuilderPreview slug={slug} base={base} sections={sections} selectedId={selectedId} onSelect={selectFromPreview} />
      </div>
    </div>
  );
}
