import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { ArrowRight, ExternalLink, Link2, Plus, Trash2 } from "lucide-react";
import apiClient from "@/services/apiClient";
import { Input } from "@/components/ui/input";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import ConfirmDialog from "@/components/shared/ConfirmDialog";
import { formatDateTime } from "@/utils/formatters";

/**
 * CMS-12 — Panel Pengalihan URL (301).
 *
 * Kenapa panel ini ada: slug = URL. Begitu editor merapikan slug artikel yang sudah diindeks
 * Google, URL lama mati 404 — peringkat pencarian & tautan dari pihak lain ikut mati. Sekarang
 * setiap perubahan slug otomatis mencatat pengalihan di sini, dan pemilik bisa menambah
 * pengalihan manual sendiri (mis. URL kampanye lama → halaman promo baru).
 *
 * Kolom “Kunjungan” = jumlah pengunjung yang TERSELAMATKAN dari halaman mati — angka nyata
 * untuk menilai apakah pengalihan masih dibutuhkan.
 */
export default function RedirectManagerPanel() {
  const [rows, setRows] = useState([]);
  const [stats, setStats] = useState({ total: 0, hits: 0 });
  const [prefixes, setPrefixes] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [saving, setSaving] = useState(false);
  const [delRow, setDelRow] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get("/content/redirects", { params: { limit: 300 } })
      .then((r) => {
        setRows(Array.isArray(r.data?.rows) ? r.data.rows : []);
        setStats(r.data?.stats || { total: 0, hits: 0 });
        setPrefixes(r.data?.prefixes || {});
        setError(null);
      })
      .catch((e) => setError(e?.response?.data?.detail || "Gagal memuat pengalihan"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const add = async () => {
    if (!from.trim() || !to.trim()) { toast.message("URL asal & tujuan wajib diisi"); return; }
    setSaving(true);
    try {
      await apiClient.post("/content/redirects", { from_path: from.trim(), to_path: to.trim() });
      toast.success("Pengalihan disimpan");
      setFrom(""); setTo("");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan pengalihan");
    } finally { setSaving(false); }
  };

  const remove = async () => {
    if (!delRow) return;
    setBusy(true);
    try {
      await apiClient.delete(`/content/redirects/${delRow.id}`);
      toast.success("Pengalihan dihapus");
      setDelRow(null);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus");
    } finally { setBusy(false); }
  };

  const kpi = (label, value, hint) => (
    <div className="section-card px-4 py-3">
      <p className="text-[10.5px] font-semibold uppercase tracking-wide text-[#8A8A8F]">{label}</p>
      <p className="mt-1 text-[22px] font-bold leading-none tabular-nums text-[#1C1C1E]">{value}</p>
      <p className="mt-1 text-[11px] text-[#6B6B73]">{hint}</p>
    </div>
  );

  return (
    <div className="space-y-4" data-testid="redirect-panel">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {kpi("Pengalihan aktif", stats.total ?? 0, "URL lama yang tetap hidup")}
        {kpi("Kunjungan terselamatkan", stats.hits ?? 0, "pengunjung yang tidak jadi 404")}
        {kpi("Otomatis", rows.filter((r) => r.kind === "auto").length,
          "dibuat sendiri saat slug diubah")}
      </div>

      <section className="section-card" data-testid="redirect-add">
        <div className="border-b border-[#F2F2F5] px-4 py-2.5">
          <p className="text-[13px] font-bold text-[#1C1C1E]">Tambah pengalihan manual</p>
          <p className="text-[11.5px] text-[#6B6B73]">
            Isi path (mulai dengan <span className="font-mono">/</span>), bukan URL lengkap.
            Contoh: <span className="font-mono">/blog/promo-lebaran</span> → <span className="font-mono">/promo</span>
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2 px-4 py-3">
          <div className="min-w-[220px] flex-1 space-y-1">
            <label className="text-[11.5px] font-semibold text-[#3A3A3C]" htmlFor="redirect-from">URL lama (asal)</label>
            <Input id="redirect-from" value={from} onChange={(e) => setFrom(e.target.value)}
              placeholder="/blog/slug-lama" data-testid="redirect-from" />
          </div>
          <ArrowRight size={16} className="mb-2 hidden text-[#8A8A8F] sm:block" />
          <div className="min-w-[220px] flex-1 space-y-1">
            <label className="text-[11.5px] font-semibold text-[#3A3A3C]" htmlFor="redirect-to">URL baru (tujuan)</label>
            <Input id="redirect-to" value={to} onChange={(e) => setTo(e.target.value)}
              placeholder="/blog/slug-baru" data-testid="redirect-to" />
          </div>
          <button className="primary-button" onClick={add} disabled={saving} data-testid="redirect-save">
            <Plus size={14} /> {saving ? "Menyimpan…" : "Simpan"}
          </button>
        </div>
        {Object.keys(prefixes).length ? (
          <p className="border-t border-[#F2F2F5] px-4 py-2 text-[11px] text-[#8A8A8F]">
            Prefiks halaman konten: {Object.entries(prefixes).map(([k, v]) => `${k} → ${v}/…`).join(" · ")}
          </p>
        ) : null}
      </section>

      {loading ? <LoadingState rows={3} testId="redirect-loading" />
        : error ? <ErrorState message={error} onRetry={load} testId="redirect-error" />
        : rows.length === 0 ? (
          <EmptyState title="Belum ada pengalihan" testId="redirect-empty"
            description="Pengalihan dibuat otomatis setiap kali Anda mengubah slug konten yang punya halaman publik. Anda juga bisa menambah pengalihan manual di atas." />
        ) : (
          <section className="section-card">
            <div className="divide-y divide-[#F2F2F5]" data-testid="redirect-list">
              {rows.map((row) => (
                <div key={row.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                  data-testid={`redirect-row-${row.id}`}>
                  <div className="min-w-0 flex-1">
                    <p className="flex flex-wrap items-center gap-2 text-[12.5px] font-semibold text-[#1C1C1E]">
                      <span className="font-mono text-[12px] text-[#A8221A]">{row.from_path}</span>
                      <ArrowRight size={12} className="text-[#8A8A8F]" />
                      <span className="font-mono text-[12px] text-[#0A7A34]">{row.to_path}</span>
                      <span className={`status-pill ${row.kind === "manual" ? "tone-info" : "tone-neutral"}`}>
                        {row.kind === "manual" ? "Manual" : "Otomatis"}
                      </span>
                    </p>
                    <p className="truncate text-[11.5px] tabular-nums text-[#6B6B73]">
                      {Number(row.hits || 0)} kunjungan diselamatkan
                      {row.last_hit_at ? ` · terakhir ${formatDateTime(row.last_hit_at)}` : ""}
                      {row.updated_at ? ` · diperbarui ${formatDateTime(row.updated_at)}` : ""}
                    </p>
                  </div>
                  <div className="flex flex-shrink-0 items-center gap-1">
                    <a className="icon-button !h-8 !w-8" href={row.from_path} target="_blank" rel="noopener noreferrer"
                      title="Coba URL lama" data-testid={`redirect-open-${row.id}`}><ExternalLink size={13} /></a>
                    <button className="icon-button !h-8 !w-8 !text-[#A8221A]" title="Hapus pengalihan"
                      onClick={() => setDelRow(row)} data-testid={`redirect-delete-${row.id}`}><Trash2 size={13} /></button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

      <p className="flex items-start gap-2 rounded-[12px] border border-[#E5E5EA] bg-[#F7F8FA] px-3 py-2.5 text-[11.5px] leading-relaxed text-[#6B6B73]">
        <Link2 size={13} className="mt-0.5 flex-shrink-0" />
        <span>
          Jujur soal teknis: situs ini SPA, jadi pengalihan dijalankan di peramban pengunjung
          (mesin pencari modern mengikutinya) dan endpoint publik menjawab niat <span className="font-semibold text-[#1C1C1E]">301</span>.
          Rantai pengalihan otomatis diratakan menjadi satu lompatan, dan lingkaran dicegah
          server — jadi tidak ada URL yang berputar-putar.
        </span>
      </p>

      <ConfirmDialog open={Boolean(delRow)} onOpenChange={(v) => !v && setDelRow(null)} busy={busy}
        title="Hapus pengalihan?"
        description={`Setelah dihapus, ${delRow?.from_path || "URL lama"} akan kembali menjadi halaman tidak ditemukan (404).`}
        onConfirm={remove} testId="redirect-confirm-delete" />
    </div>
  );
}
