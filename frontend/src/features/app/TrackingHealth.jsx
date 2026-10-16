import { useCallback, useEffect, useState } from "react";
import { Activity, RefreshCw, Send, CheckCircle2, XCircle, Clock, MinusCircle, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { LoadingState, ErrorState, EmptyState } from "@/components/shared/DataStates";
import SelectField from "@/components/shared/SelectField";
import { formatDateTime, formatCurrency } from "@/utils/formatters";

/**
 * TrackingHealth.jsx — "Kesehatan Pelacakan".
 *
 * Tujuan: TIDAK ADA konversi yang hilang diam-diam. Setiap percobaan kirim ke Meta/Google
 * tercatat beserta alasan gagalnya, bisa dicoba ulang, dan bisa diuji dengan event uji
 * (Meta: test_event_code · Google: validateOnly — tidak mengotori data produksi).
 */
const STATUS_META = {
  success: { label: "Terkirim", icon: CheckCircle2, cls: "bg-[#E7F7EC] text-[#12703A]" },
  failed: { label: "Gagal (antre ulang)", icon: XCircle, cls: "bg-[#FDECEA] text-[#A8221A]" },
  dead: { label: "Perlu tindakan", icon: AlertTriangle, cls: "bg-[#FDECEA] text-[#A8221A]" },
  pending: { label: "Menunggu", icon: Clock, cls: "bg-[#EAF2FF] text-[#0B5BD3]" },
  skipped: { label: "Dilewati", icon: MinusCircle, cls: "bg-[#F2F2F5] text-[#6B6B73]" },
};
const KINDS = [
  { value: "lead", label: "Lead terkirim" },
  { value: "booking", label: "Booking dikonfirmasi" },
  { value: "payment", label: "DP / pembayaran diterima" },
];
const STATUS_FILTER = [
  { value: "", label: "Semua status" },
  { value: "pending", label: "Menunggu" },
  { value: "success", label: "Terkirim" },
  { value: "failed", label: "Gagal (antre ulang)" },
  { value: "skipped", label: "Dilewati" },
  { value: "dead", label: "Perlu tindakan" },
];
const PROVIDER_FILTER = [
  { value: "", label: "Semua platform" },
  { value: "meta", label: "Meta" },
  { value: "google", label: "Google" },
];

function Pill({ status }) {
  const m = STATUS_META[status] || STATUS_META.pending;
  const Icon = m.icon;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${m.cls}`}
      data-testid={`th-status-${status}`}>
      <Icon size={11} /> {m.label}
    </span>
  );
}

function Stat({ provider, counts, readiness }) {
  const total = Object.values(counts || {}).reduce((a, b) => a + b, 0);
  const live = readiness?.mode === "live";
  return (
    <div className="rounded-xl border border-[#EFF0F2] bg-white p-3.5" data-testid={`th-card-${provider}`}>
      <div className="flex items-center justify-between">
        <p className="text-[12.5px] font-bold text-[#1C1C1E]">{provider === "meta" ? "Meta (Pixel/CAPI)" : "Google (Data Manager)"}</p>
        <span className={`rounded-full px-2 py-0.5 text-[10.5px] font-bold uppercase ${live ? "bg-[#E7F7EC] text-[#12703A]" : "bg-[#FFF3E0] text-[#8A5300]"}`}>
          {live ? "AKTIF" : "MOCK"}
        </span>
      </div>
      <p className="mt-2 text-[22px] font-bold tabular-nums text-[#1C1C1E]">{counts?.success || 0}
        <span className="text-[12px] font-medium text-[#8E8E93]"> / {total} terkirim</span></p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {Object.entries(counts || {}).filter(([, n]) => n > 0).map(([s, n]) => (
          <span key={s} className="rounded-md bg-[#F7F8FA] px-1.5 py-0.5 text-[11px] tabular-nums text-[#6B6B73]">
            {(STATUS_META[s] || {}).label || s}: {n}
          </span>
        ))}
      </div>
      {readiness?.missing?.length ? (
        <p className="mt-2 text-[11.5px] text-[#8A5300]">Belum lengkap: {readiness.missing.join(", ")}</p>
      ) : null}
    </div>
  );
}

export default function TrackingHealth() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [kind, setKind] = useState("lead");
  const [statusFilter, setStatusFilter] = useState("");
  const [providerFilter, setProviderFilter] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    const q = `?limit=40${statusFilter ? `&status=${statusFilter}` : ""}${providerFilter ? `&provider=${providerFilter}` : ""}`;
    apiClient.get(`/tracking/health${q}`)
      .then((r) => { setData(r.data); setError(null); })
      .catch((e) => setError(e?.response?.data?.detail || "Gagal memuat kesehatan pelacakan"))
      .finally(() => setLoading(false));
  }, [statusFilter, providerFilter]);
  useEffect(load, [load]);

  const runWorker = async () => {
    setBusy(true);
    try {
      const { data: res } = await apiClient.post("/tracking/dispatch");
      const p = res?.processed || {};
      toast.success(`Pekerja dijalankan — terkirim ${p.success || 0}, gagal ${p.failed || 0}, dilewati ${p.skipped || 0}`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menjalankan pekerja konversi");
    } finally { setBusy(false); }
  };

  const sendTest = async () => {
    setBusy(true);
    try {
      const { data: res } = await apiClient.post("/tracking/test-event", { kind, value: kind === "lead" ? 0 : 1500000 });
      const lines = Object.entries(res.results || {}).map(([p, r]) => `${p}: ${r.status}`).join(" · ");
      toast.success(`Event uji dikirim — ${lines || "tidak ada provider aktif"}`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengirim event uji");
    } finally { setBusy(false); }
  };

  const retry = async (id) => {
    try {
      const { data: res } = await apiClient.post(`/tracking/retry/${id}`);
      toast.success(`Percobaan ulang: ${res.status}`);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal mencoba ulang"); }
  };

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  const rows = data?.attempts || [];
  return (
    <div className="space-y-5" data-testid="tracking-page">
      <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
        <Stat provider="meta" counts={data?.summary?.meta} readiness={data?.readiness?.meta} />
        <Stat provider="google" counts={data?.summary?.google} readiness={data?.readiness?.google} />
      </div>

      <section className="section-card">
        <div className="section-head">
          <h2 className="flex items-center gap-2"><Send size={15} /> Kirim Event Uji</h2>
          <p className="mt-0.5 text-[12px] font-normal text-[#6B6B73]">
            Meta memakai <b>test_event_code</b>, Google memakai <b>validateOnly</b> — aman, tidak mengotori data produksi.
          </p>
        </div>
        <div className="section-body flex flex-wrap items-end gap-2">
          <div className="w-[240px]">
            <SelectField value={kind} onChange={setKind} options={KINDS} testId="th-kind" className="w-full" />
          </div>
          <button className="primary-button" onClick={sendTest} disabled={busy} data-testid="th-send-test">
            <Send size={14} /> {busy ? "Mengirim…" : "Kirim Event Uji"}
          </button>
          <button className="secondary-button" onClick={runWorker} disabled={busy} data-testid="th-run-worker">
            <RefreshCw size={14} /> Jalankan Pekerja Sekarang
          </button>
          <button className="secondary-button" onClick={load} data-testid="th-refresh"><RefreshCw size={14} /> Muat ulang</button>
        </div>
        {data?.worker?.last_run_at ? (
          <div className="section-body pt-0 text-[11.5px] text-[#6B6B73]" data-testid="th-worker-state">
            Pekerja otomatis terakhir jalan {formatDateTime(data.worker.last_run_at)} ({data.worker.source === "manual" ? "manual" : "terjadwal"})
            — terkirim {data.worker.success || 0}, gagal {data.worker.failed || 0}, dilewati {data.worker.skipped || 0}.
            Pekerja berjalan otomatis tiap 2 menit untuk mengirim ulang konversi yang gagal.
          </div>
        ) : (
          <div className="section-body pt-0 text-[11.5px] text-[#6B6B73]" data-testid="th-worker-state">
            Pekerja otomatis berjalan tiap 2 menit; belum ada catatan eksekusi.
          </div>
        )}
      </section>

      <section className="section-card">
        <div className="section-head flex flex-wrap items-center justify-between gap-2">
          <h2 className="flex items-center gap-2"><Activity size={15} /> Percobaan Terakhir</h2>
          <div className="flex flex-wrap gap-2">
            <div className="w-[170px]">
              <SelectField value={statusFilter} onChange={setStatusFilter} options={STATUS_FILTER} testId="th-filter-status" className="w-full" />
            </div>
            <div className="w-[160px]">
              <SelectField value={providerFilter} onChange={setProviderFilter} options={PROVIDER_FILTER} testId="th-filter-provider" className="w-full" />
            </div>
          </div>
        </div>
        <div className="section-body">
          {!rows.length ? (
            <EmptyState title="Belum ada percobaan konversi"
              description="Percobaan akan muncul otomatis saat ada lead, booking dikonfirmasi, atau pembayaran masuk." />
          ) : (
            <div className="divide-y divide-[#F0F1F3]" data-testid="th-list">
              {rows.map((r) => (
                <div key={r.id} className="flex flex-wrap items-start justify-between gap-3 py-3" data-testid={`th-row-${r.id}`}>
                  <div className="min-w-0">
                    <p className="flex flex-wrap items-center gap-2 text-[13px] font-semibold text-[#1C1C1E]">
                      {r.provider === "meta" ? "Meta" : "Google"} · {r.event_name}
                      <Pill status={r.status} />
                      {r.value ? <span className="tabular-nums text-[12px] font-normal text-[#6B6B73]">{formatCurrency(r.value)}</span> : null}
                    </p>
                    <p className="mt-0.5 text-[11.5px] text-[#8E8E93]">
                      {r.event_key} · {formatDateTime(r.created_at)}
                      {r.attempts ? ` · percobaan ${r.attempts}/${data?.max_attempts || 5}` : ""}
                    </p>
                    {r.last_error ? <p className="mt-1 text-[11.5px] text-[#A8221A]">{r.last_error}</p> : null}
                  </div>
                  {["failed", "dead", "skipped"].includes(r.status) ? (
                    <button className="secondary-button !h-8" onClick={() => retry(r.id)} data-testid={`th-retry-${r.id}`}>
                      <RefreshCw size={13} /> Coba lagi
                    </button>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
