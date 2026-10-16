import { useCallback, useEffect, useState } from "react";
import { MapPin, Landmark, Building2, Loader2, Pencil, Check, X, Power, Merge, Undo2, FileSpreadsheet } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { LoadingState, ErrorState } from "@/components/shared/DataStates";
import AddonMasterPanel from "@/components/app/AddonMasterPanel";

// Master Data referensi (INV-REF-02): SATU tempat kelola titik jemput, destinasi & kota.
// Rename di sini CASCADE ke dokumen pemakai; nonaktif = hilang dari selector form.
// Batch 5: panel Kota, GABUNG destinasi kembar, ekspor Excel.

function usageLabel(row, kind) {
  if (kind === "pickup") return `${row.used_by_bookings} booking`;
  if (kind === "city") return `${row.used_by_customers} pelanggan · ${row.used_by_partners} mitra · ${row.used_by_workshops || 0} bengkel`;
  return `${row.used_by_bookings} booking · ${row.used_by_leads} lead · ${row.used_by_quotations || 0} penawaran`;
}

function totalUsage(row, kind) {
  if (kind === "pickup") return row.used_by_bookings || 0;
  if (kind === "city") return (row.used_by_customers || 0) + (row.used_by_partners || 0) + (row.used_by_workshops || 0);
  return (row.used_by_bookings || 0) + (row.used_by_leads || 0) + (row.used_by_quotations || 0);
}

function MergePanel({ row, kind, siblings, busy, onMerge, onClose }) {
  const [targetId, setTargetId] = useState("");
  const target = siblings.find((s) => s.id === targetId);
  const word = kind === "pickup" ? "titik jemput" : "destinasi";
  return (
    <div className="w-full rounded-lg border border-[#C9DDF5] bg-[#EFF6FF] px-3 py-2 text-[12px] text-[#12406E]"
      data-testid={`md-merge-panel-${row.id}`}>
      Gabungkan "<b>{row.name}</b>" ke {word} lain — {usageLabel(row, kind)} milik "{row.name}" akan
      pindah memakai nama target, lalu baris ini dinonaktifkan (tidak ada data yang dihapus).
      <div className="mt-1.5 flex flex-wrap items-center gap-2">
        <div className="min-w-[220px]">
          <Select value={targetId} onValueChange={setTargetId}>
            <SelectTrigger className="!h-8 bg-white text-[12.5px]" data-testid={`md-merge-target-${row.id}`}>
              <SelectValue placeholder={`Pilih ${word} target…`} />
            </SelectTrigger>
            <SelectContent>
              {siblings.map((s) => (
                <SelectItem key={s.id} value={s.id} data-testid={`md-merge-target-opt-${s.id}`}>{s.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <button className="primary-button !h-8 !px-3 !text-[11.5px]" disabled={busy || !targetId}
          onClick={() => onMerge(row, target)} data-testid={`md-merge-confirm-${row.id}`}>
          <Merge size={12} /> Gabungkan
        </button>
        <button className="secondary-button !h-8 !px-3 !text-[11.5px]" onClick={onClose}
          data-testid={`md-merge-cancel-${row.id}`}>Batal</button>
      </div>
    </div>
  );
}

function Row({ row, kind, busy, onRename, onToggle, onMerge, onUnmerge, mergeTargets }) {
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [merging, setMerging] = useState(false);
  const [unmerging, setUnmerging] = useState(false);
  const [name, setName] = useState(row.name || "");
  const active = kind === "dest" ? row.ops_active : row.active;
  const merged = kind !== "city" && !!row.merged_into;
  const save = () => {
    const clean = name.trim();
    if (clean.length < 2 || clean === row.name) { setEditing(false); setName(row.name); return; }
    setConfirming(true);
  };
  const confirmRename = () => { onRename(row, name.trim()); setConfirming(false); setEditing(false); };
  return (
    <div className={`flex flex-wrap items-center gap-2 border-b border-[#F2F2F5] px-3 py-2.5 last:border-0 ${active ? "" : "opacity-55"}`}
      data-testid={`md-row-${row.id}`}>
      <div className="min-w-[200px] flex-1">
        {editing ? (
          <div className="flex items-center gap-1.5">
            <Input className="!h-8 max-w-[260px] text-[13px]" value={name} onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && save()} autoFocus data-testid={`md-rename-input-${row.id}`} />
            <button className="icon-button !h-8 !w-8" onClick={save} data-testid={`md-rename-save-${row.id}`}><Check size={14} /></button>
            <button className="icon-button !h-8 !w-8" onClick={() => { setEditing(false); setConfirming(false); setName(row.name); }} data-testid={`md-rename-abort-${row.id}`}><X size={14} /></button>
          </div>
        ) : (
          <>
            <span className="text-[13.5px] font-semibold text-[#1C1C1E]" data-testid={`md-name-${row.id}`}>{row.name}</span>
            {kind === "dest" && row.status === "draft" ? (
              <span className="ml-2 rounded-full bg-[#F2F2F5] px-2 py-0.5 text-[10.5px] font-semibold text-[#6B6B73]">ops / draft</span>
            ) : null}
            {merged ? (
              <span className="ml-2 rounded-full bg-[#EFF6FF] px-2 py-0.5 text-[10.5px] font-semibold text-[#12406E]"
                data-testid={`md-merged-badge-${row.id}`}>Digabung → {row.merged_into_name}</span>
            ) : null}
            <span className="block text-[11px] text-[#8E8E93]">Dipakai: {usageLabel(row, kind)}</span>
          </>
        )}
      </div>
      {!active && !merged ? <span className="rounded-full bg-[#FF3B30]/10 px-2 py-0.5 text-[11px] font-semibold text-[#A8221A]">Nonaktif</span> : null}
      {merged ? (
        <button className="secondary-button !h-8 !px-2.5 !text-[11.5px]" disabled={busy}
          onClick={() => setUnmerging((v) => !v)} data-testid={`md-unmerge-${row.id}`}>
          <Undo2 size={12} /> Batalkan Gabungan
        </button>
      ) : null}
      {!merged ? (
        <>
          <button className="secondary-button !h-8 !px-2.5 !text-[11.5px]" disabled={busy || editing}
            onClick={() => setEditing(true)} data-testid={`md-rename-${row.id}`}><Pencil size={12} /> Ganti Nama</button>
          {kind !== "city" ? (
            <button className="secondary-button !h-8 !px-2.5 !text-[11.5px]" disabled={busy || editing}
              onClick={() => setMerging((v) => !v)} data-testid={`md-merge-${row.id}`}><Merge size={12} /> Gabung</button>
          ) : null}
          <button className="secondary-button !h-8 !px-2.5 !text-[11.5px]" disabled={busy}
            onClick={() => onToggle(row, !active)} data-testid={`md-toggle-${row.id}`}>
            <Power size={12} /> {active ? "Nonaktifkan" : "Aktifkan"}
          </button>
        </>
      ) : null}
      {confirming ? (
        <div className="w-full rounded-lg border border-[#F5D08C] bg-[#FFF7E6] px-3 py-2 text-[12px] text-[#7A5A00]"
          data-testid={`md-confirm-${row.id}`}>
          Ganti "<b>{row.name}</b>" → "<b>{name.trim()}</b>"?{" "}
          {totalUsage(row, kind) > 0
            ? <>Ini akan ikut memperbarui <b>{usageLabel(row, kind)}</b> yang memakai nama lama.</>
            : <>Belum ada dokumen yang memakai nama ini — aman diganti.</>}
          <div className="mt-1.5 flex gap-2">
            <button className="primary-button !h-7 !px-3 !text-[11.5px]" disabled={busy}
              onClick={confirmRename} data-testid={`md-rename-confirm-${row.id}`}>Ya, Ganti Nama</button>
            <button className="secondary-button !h-7 !px-3 !text-[11.5px]"
              onClick={() => setConfirming(false)} data-testid={`md-rename-cancel-${row.id}`}>Batal</button>
          </div>
        </div>
      ) : null}
      {merging && !merged ? (
        <MergePanel row={row} kind={kind} busy={busy} onClose={() => setMerging(false)}
          siblings={(mergeTargets || []).filter((s) => s.id !== row.id && !s.merged_into
            && (kind === "pickup" ? s.active : s.ops_active))}
          onMerge={(src, tgt) => { onMerge(src, tgt); setMerging(false); }} />
      ) : null}
      {unmerging && merged ? (
        <div className="w-full rounded-lg border border-[#C9DDF5] bg-[#EFF6FF] px-3 py-2 text-[12px] text-[#12406E]"
          data-testid={`md-unmerge-panel-${row.id}`}>
          Kembalikan "<b>{row.name}</b>" sebagai {kind === "pickup" ? "titik jemput" : "destinasi"} aktif?{" "}
          {row.merged_moved_count > 0
            ? <><b>{row.merged_moved_count} dokumen</b> yang ikut pindah ke "{row.merged_into_name}" akan dikembalikan memakai nama ini (dokumen yang sudah diubah manual setelah gabungan tidak disentuh).</>
            : <>Tidak ada dokumen yang ikut pindah — baris ini hanya diaktifkan kembali.</>}
          <div className="mt-1.5 flex gap-2">
            <button className="primary-button !h-7 !px-3 !text-[11.5px]" disabled={busy}
              onClick={() => { onUnmerge(row); setUnmerging(false); }} data-testid={`md-unmerge-confirm-${row.id}`}>Ya, Batalkan Gabungan</button>
            <button className="secondary-button !h-7 !px-3 !text-[11.5px]"
              onClick={() => setUnmerging(false)} data-testid={`md-unmerge-cancel-${row.id}`}>Batal</button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Panel({ icon: Icon, title, desc, kind, rows, busy, onRename, onToggle, onMerge, onUnmerge, testId }) {
  return (
    <section className="rounded-[14px] border border-[#EFF0F2] bg-white shadow-sm" data-testid={testId}>
      <div className="border-b border-[#EFF0F2] px-4 py-3">
        <h2 className="flex items-center gap-2 text-[14px] font-bold text-[#1C1C1E]" style={{ fontFamily: "Outfit, sans-serif" }}>
          <Icon size={15} className="text-[#007AFF]" /> {title}
          <span className="rounded-full bg-[#EAF2FF] px-2 py-0.5 text-[11px] font-semibold text-[#0058CC]">{rows.length}</span>
        </h2>
        <p className="mt-0.5 text-[12px] text-[#6B6B73]">{desc}</p>
      </div>
      <div>
        {rows.map((r) => <Row key={r.id} row={r} kind={kind} busy={busy} onRename={onRename} onToggle={onToggle} onMerge={onMerge} onUnmerge={onUnmerge} mergeTargets={rows} />)}
        {rows.length === 0 ? <p className="px-4 py-5 text-[12.5px] text-[#8E8E93]">Belum ada data.</p> : null}
      </div>
    </section>
  );
}

export default function MasterData() {
  const [pickups, setPickups] = useState([]);
  const [dests, setDests] = useState([]);
  const [cities, setCities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [p, d, c] = await Promise.all([
        apiClient.get("/master/pickup-points"),
        apiClient.get("/master/destinations"),
        apiClient.get("/master/cities"),
      ]);
      setPickups(Array.isArray(p.data) ? p.data : []);
      setDests(Array.isArray(d.data) ? d.data : []);
      setCities(Array.isArray(c.data) ? c.data : []);
    } catch (e) {
      setError(e?.response?.data?.detail || "Gagal memuat master data");
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const act = async (fn, okMsg) => {
    setBusy(true);
    try { const extra = await fn(); toast.success(okMsg + (extra || "")); await load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Gagal menyimpan"); }
    finally { setBusy(false); }
  };
  const renamePickup = (row, name) => act(async () => {
    const { data } = await apiClient.patch(`/master/pickup-points/${row.id}`, { name });
    return data.cascaded_bookings ? ` · ${data.cascaded_bookings} booking ikut diperbarui` : "";
  }, `Titik jemput → "${name}"`);
  const togglePickup = (row, active) => act(async () => {
    await apiClient.patch(`/master/pickup-points/${row.id}`, { active });
  }, active ? `"${row.name}" diaktifkan` : `"${row.name}" dinonaktifkan`);
  const mergePickup = (row, target) => act(async () => {
    const { data } = await apiClient.post(`/master/pickup-points/${row.id}/merge`, { target_id: target.id });
    return ` · ${data.cascade?.bookings || 0} booking pindah ke "${data.target}"`;
  }, `"${row.name}" digabung`);
  const unmergePickup = (row) => act(async () => {
    const { data } = await apiClient.post(`/master/pickup-points/${row.id}/unmerge`);
    return ` · ${data.restored?.bookings || 0} booking kembali${data.skipped ? ` (${data.skipped} dilewati)` : ""}`;
  }, `Gabungan "${row.name}" dibatalkan`);
  const renameDest = (row, name) => act(async () => {
    const { data } = await apiClient.patch(`/master/destinations/${row.id}`, { name });
    const n = Object.values(data.cascade || {}).reduce((a, b) => a + b, 0);
    return n ? ` · ${n} dokumen ikut diperbarui` : "";
  }, `Destinasi → "${name}"`);
  const toggleDest = (row, ops_active) => act(async () => {
    await apiClient.patch(`/master/destinations/${row.id}`, { ops_active });
  }, ops_active ? `"${row.name}" diaktifkan` : `"${row.name}" dinonaktifkan`);
  const mergeDest = (row, target) => act(async () => {
    const { data } = await apiClient.post(`/master/destinations/${row.id}/merge`, { target_id: target.id });
    const n = Object.values(data.cascade || {}).reduce((a, b) => a + b, 0);
    return ` · ${n} dokumen pindah ke "${data.target}"`;
  }, `"${row.name}" digabung`);
  const unmergeDest = (row) => act(async () => {
    const { data } = await apiClient.post(`/master/destinations/${row.id}/unmerge`);
    const n = Object.values(data.restored || {}).reduce((a, b) => a + b, 0);
    return ` · ${n} dokumen kembali${data.skipped ? ` (${data.skipped} dilewati)` : ""}`;
  }, `Gabungan "${row.name}" dibatalkan`);
  const renameCity = (row, name) => act(async () => {
    const { data } = await apiClient.patch(`/master/cities/${row.id}`, { name });
    const n = Object.values(data.cascade || {}).reduce((a, b) => a + b, 0);
    return n ? ` · ${n} dokumen ikut diperbarui` : "";
  }, `Kota → "${name}"`);
  const toggleCity = (row, active) => act(async () => {
    await apiClient.patch(`/master/cities/${row.id}`, { active });
  }, active ? `"${row.name}" diaktifkan` : `"${row.name}" dinonaktifkan`);

  const exportExcel = async () => {
    setExporting(true);
    try {
      const res = await apiClient.get("/master/export", { responseType: "blob" });
      const url = window.URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url; a.download = "master-data-rahazatrans.xlsx";
      document.body.appendChild(a); a.click(); a.remove();
      window.URL.revokeObjectURL(url);
      toast.success("Master data diunduh (Excel)");
    } catch { toast.error("Gagal mengekspor master data"); }
    finally { setExporting(false); }
  };

  if (loading) return <LoadingState testId="masterdata-loading" />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div className="space-y-5" data-testid="masterdata-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="max-w-3xl text-[13px] text-[#6B6B73]">
          Satu pintu referensi form (SSOT). <b>Ganti nama</b> otomatis memperbarui dokumen yang memakai
          nama lama (dengan pratinjau jumlah); <b>Gabung</b> menyatukan destinasi kembar beserta riwayatnya;
          <b> Nonaktifkan</b> menyembunyikan dari pilihan form tanpa mengubah data lama.
        </p>
        <button className="secondary-button !h-9 !px-3 !text-[12px]" disabled={exporting}
          onClick={exportExcel} data-testid="md-export-excel">
          {exporting ? <Loader2 size={13} className="animate-spin" /> : <FileSpreadsheet size={13} />} Unduh Excel
        </button>
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Panel icon={MapPin} title="Titik Jemput" kind="pickup" rows={pickups} busy={busy}
          desc="Dipakai field 'Titik Jemput' pada booking. Gabung menyatukan titik jemput kembar (bisa dibatalkan). Tambah cepat tersedia langsung di form booking."
          onRename={renamePickup} onToggle={togglePickup} onMerge={mergePickup} onUnmerge={unmergePickup} testId="md-pickup-panel" />
        <Panel icon={Building2} title="Kota" kind="city" rows={cities} busy={busy}
          desc="Dipakai field 'Kota' pada pelanggan & mitra. Tambah cepat tersedia langsung di form."
          onRename={renameCity} onToggle={toggleCity} testId="md-city-panel" />
        <Panel icon={Landmark} title="Destinasi (sisi ops)" kind="dest" rows={dests} busy={busy}
          desc="Dipakai booking, lead CRM, penawaran & form web. Gabung menyatukan destinasi kembar (bisa dibatalkan). Konten halaman web dikelola di Konten Web; nonaktif di sini tidak menurunkan halaman publik."
          onRename={renameDest} onToggle={toggleDest} onMerge={mergeDest} onUnmerge={unmergeDest} testId="md-dest-panel" />
        <AddonMasterPanel />
      </div>
    </div>
  );
}
