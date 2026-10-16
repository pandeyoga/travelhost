import { useState } from "react";
import { Megaphone, PauseCircle, PlayCircle } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { EmptyState, LoadingState } from "@/components/shared/DataStates";
import { formatQty } from "@/utils/formatters";
import { moneyText } from "@/features/app/Ads";
import ConfirmNameDialog from "@/components/app/ads/ConfirmNameDialog";

/**
 * AdsPerformance — tabel inti: biaya platform ⨯ hasil bisnis ERP per entitas iklan.
 * Kolom "Lead→Booking" menjawab pertanyaan mahal: iklan mana yang ramai lead tapi tak pernah jadi?
 * Tombol Aktifkan memakai pengaman: wajib mengetik ulang nama objek (uang akan berjalan).
 */
const PROVIDER_LABEL = { meta: "Meta", google: "Google" };

export default function AdsPerformance({ performance, currency, canManage, onChanged, loading }) {
  const [busy, setBusy] = useState("");
  const [confirmRow, setConfirmRow] = useState(null);
  const rows = performance?.rows || [];

  const totals = performance?.totals || {};
  const levelLabel = performance?.level === "ad" ? "Iklan"
    : performance?.level === "adset" ? "Adset / Ad Group" : "Kampanye";

  const apply = async (row, status, confirmName) => {
    setBusy(row.entity_id);
    try {
      const { data } = await apiClient.post("/ads/campaigns/status", {
        provider: row.provider, object_id: row.entity_id, status,
        confirm_name: confirmName || "", expected_name: row.name,
      });
      const res = data?.result || {};
      if (res.status === "ok") toast.success(`Status diubah menjadi ${data.status}`);
      else toast.warning(res.reason || `Belum bisa diubah (${res.status})`);
      onChanged?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengubah status iklan");
    } finally { setBusy(""); setConfirmRow(null); }
  };

  if (loading) return <LoadingState testId="ads-perf-loading" />;
  if (!rows.length) {
    return (
      <EmptyState title="Belum ada baris performa iklan" testId="ads-perf-empty"
        description="Baris muncul setelah metrik ditarik dari platform, atau setelah ada lead ber-atribusi iklan (Lead Ads, Klik-ke-WhatsApp, atau UTM dari landing page)." />
    );
  }

  return (
    <section className="section-card" data-testid="ads-perf">
      <div className="section-head">
        <h2 className="flex items-center gap-2"><Megaphone size={15} /> Performa per {levelLabel}</h2>
        <p className="mt-0.5 text-[12px] font-normal text-[#6B6B73]">
          Booking &amp; pendapatan berasal dari data ERP (bukan klaim platform) — jadi ROAS di sini adalah ROAS nyata.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-[12.5px]">
          <thead>
            <tr className="border-b border-[#EFF0F2] text-left text-[11px] uppercase tracking-wide text-[#8E8E93]">
              <th className="px-4 py-2.5">Nama</th>
              <th className="px-3 py-2.5">Platform</th>
              <th className="px-3 py-2.5 text-right">Biaya</th>
              <th className="px-3 py-2.5 text-right">Klik</th>
              <th className="px-3 py-2.5 text-right">Lead</th>
              <th className="px-3 py-2.5 text-right">Booking</th>
              <th className="px-3 py-2.5 text-right">Pendapatan</th>
              <th className="px-3 py-2.5 text-right">CPL</th>
              <th className="px-3 py-2.5 text-right">CAC</th>
              <th className="px-3 py-2.5 text-right">ROAS</th>
              <th className="px-3 py-2.5 text-right">Lead→Booking</th>
              {canManage ? <th className="px-3 py-2.5 text-right">Aksi</th> : null}
            </tr>
          </thead>
          <tbody data-testid="ads-perf-list">
            {rows.map((r) => (
              <tr key={`${r.provider}-${r.entity_id}`} className="border-b border-[#F6F6F8] hover:bg-[#FAFAFB]"
                data-testid={`ads-perf-row-${r.entity_id}`}>
                <td className="px-4 py-2.5">
                  <div className="font-semibold text-[#1C1C1E]">{r.name}</div>
                  <div className="text-[11px] text-[#8E8E93]">{r.entity_id}</div>
                </td>
                <td className="px-3 py-2.5">{PROVIDER_LABEL[r.provider] || r.provider || "—"}</td>
                <td className="px-3 py-2.5 text-right font-semibold tabular-nums">{moneyText(r.spend, r.currency || currency)}</td>
                <td className="px-3 py-2.5 text-right tabular-nums">{formatQty(r.clicks)}</td>
                <td className="px-3 py-2.5 text-right tabular-nums">{formatQty(r.leads)}</td>
                <td className="px-3 py-2.5 text-right tabular-nums">{formatQty(r.bookings)}</td>
                <td className="px-3 py-2.5 text-right tabular-nums">{moneyText(r.revenue, "IDR")}</td>
                <td className="px-3 py-2.5 text-right tabular-nums">{r.cpl != null ? moneyText(r.cpl, r.currency || currency) : "—"}</td>
                <td className="px-3 py-2.5 text-right tabular-nums">{r.cac != null ? moneyText(r.cac, r.currency || currency) : "—"}</td>
                <td className="px-3 py-2.5 text-right font-semibold tabular-nums"
                  style={{ color: r.roas == null ? "#8E8E93" : r.roas >= 1 ? "#126E2C" : "#A8221A" }}>
                  {r.roas != null ? `${r.roas}×` : "—"}
                </td>
                <td className="px-3 py-2.5 text-right tabular-nums">{r.lead_to_booking != null ? `${r.lead_to_booking}%` : "—"}</td>
                {canManage ? (
                  <td className="px-3 py-2.5 text-right">
                    <div className="flex justify-end gap-1.5">
                      <button className="secondary-button !h-8" disabled={busy === r.entity_id}
                        onClick={() => apply(r, "PAUSED", "")} data-testid={`ads-pause-${r.entity_id}`}>
                        <PauseCircle size={13} /> Jeda
                      </button>
                      <button className="secondary-button !h-8" disabled={busy === r.entity_id}
                        onClick={() => setConfirmRow(r)} data-testid={`ads-activate-${r.entity_id}`}>
                        <PlayCircle size={13} /> Aktifkan
                      </button>
                    </div>
                  </td>
                ) : null}
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="bg-[#FAFAFB] text-[12.5px] font-bold">
              <td className="px-4 py-2.5" colSpan={2}>Total</td>
              <td className="px-3 py-2.5 text-right tabular-nums">{moneyText(totals.spend, currency)}</td>
              <td className="px-3 py-2.5 text-right tabular-nums">{formatQty(totals.clicks)}</td>
              <td className="px-3 py-2.5 text-right tabular-nums">{formatQty(totals.leads)}</td>
              <td className="px-3 py-2.5 text-right tabular-nums">{formatQty(totals.bookings)}</td>
              <td className="px-3 py-2.5 text-right tabular-nums">{moneyText(totals.revenue, "IDR")}</td>
              <td className="px-3 py-2.5 text-right tabular-nums">{totals.cpl != null ? moneyText(totals.cpl, currency) : "—"}</td>
              <td className="px-3 py-2.5 text-right tabular-nums">{totals.cac != null ? moneyText(totals.cac, currency) : "—"}</td>
              <td className="px-3 py-2.5 text-right tabular-nums">{totals.roas != null ? `${totals.roas}×` : "—"}</td>
              <td className="px-3 py-2.5" colSpan={canManage ? 2 : 1} />
            </tr>
          </tfoot>
        </table>
      </div>

      <ConfirmNameDialog
        open={Boolean(confirmRow)}
        expectedName={confirmRow?.name || ""}
        title="Aktifkan iklan ini?"
        description="Setelah aktif, platform akan mulai membelanjakan budget harian. Ketik ulang nama objek untuk memastikan Anda tidak salah klik."
        actionLabel="Aktifkan Sekarang"
        testId="ads-activate-confirm"
        onCancel={() => setConfirmRow(null)}
        onConfirm={(typed) => apply(confirmRow, "ACTIVE", typed)}
      />
    </section>
  );
}
