import { useState } from "react";
import { Wallet, Save } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { EmptyState, LoadingState } from "@/components/shared/DataStates";
import { formatQty } from "@/utils/formatters";
import { moneyText } from "@/features/app/Ads";

/**
 * AdsManualSpend — biaya iklan MANUAL per channel.
 * Alasan tetap ada: sebelum kredensial API diisi (atau untuk channel di luar Meta/Google seperti
 * TikTok & endorse), ROAS masih bisa dihitung nyata karena pendapatan sudah diketahui ERP.
 */
const CHANNELS = [
  ["meta_ads", "Meta Ads (FB/IG)"],
  ["google_ads", "Google Ads"],
  ["tiktok_ads", "TikTok Ads"],
  ["whatsapp", "WhatsApp / Broadcast"],
  ["referral", "Referral / Endorse"],
];

export default function AdsManualSpend({ spend, canManage, onSaved, loading }) {
  const [draft, setDraft] = useState({});
  const [busy, setBusy] = useState(false);
  const map = spend?.spend_map || {};
  const rows = spend?.items || [];

  const save = async () => {
    setBusy(true);
    try {
      const items = CHANNELS.map(([key]) => ({
        channel: key, amount: Number(draft[key] ?? map[key] ?? 0) || 0,
      })).filter((i) => i.amount > 0);
      await apiClient.put("/ads/manual-spend", { items, note: "Diisi dari Dashboard Iklan" });
      toast.success("Biaya iklan manual disimpan");
      setDraft({});
      onSaved?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan biaya iklan");
    } finally { setBusy(false); }
  };

  if (loading) return <LoadingState testId="ads-manual-loading" />;
  return (
    <section className="section-card" data-testid="ads-manual-spend">
      <div className="section-head">
        <h2 className="flex items-center gap-2"><Wallet size={15} /> Biaya Iklan Manual (sumber cadangan)</h2>
        <p className="mt-0.5 text-[12px] font-normal text-[#6B6B73]">
          Dipakai menghitung CPL/CAC/ROAS per channel saat API platform belum aktif, atau untuk channel di luar Meta &amp; Google.
        </p>
      </div>
      <div className="section-body space-y-3">
        {!canManage ? (
          rows.length ? (
            <div className="divide-y divide-[#F0F1F3]" data-testid="ads-manual-readonly">
              {rows.map((i) => (
                <div key={i.channel} className="flex items-center justify-between py-2 text-[12.5px]">
                  <span className="text-[#3C3C43]">{i.channel}</span>
                  <span className="font-semibold tabular-nums">{moneyText(i.amount, "IDR")}</span>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="Belum ada biaya manual" testId="ads-manual-empty"
              description="Hanya owner & marketing admin yang dapat mengisi biaya iklan." />
          )
        ) : (
          <>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {CHANNELS.map(([key, label]) => (
                <div key={key} className="space-y-1.5">
                  <label className="text-[12px] font-semibold text-[#3a3f4a]" htmlFor={`spend-${key}`}>{label}</label>
                  <input id={`spend-${key}`} type="number" min="0" step="1000" data-testid={`ads-spend-${key}`}
                    value={draft[key] ?? map[key] ?? ""}
                    onChange={(e) => setDraft((d) => ({ ...d, [key]: e.target.value }))}
                    placeholder="0"
                    className="h-9 w-full rounded-lg border border-[#E5E5EA] bg-white px-3 text-[13px] tabular-nums outline-none focus:border-[#007AFF]" />
                </div>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button className="primary-button" onClick={save} disabled={busy} data-testid="ads-spend-save">
                <Save size={14} /> {busy ? "Menyimpan…" : "Simpan Biaya"}
              </button>
              <span className="text-[11.5px] text-[#8E8E93]">
                Tersimpan: <b className="tabular-nums">{moneyText(spend?.total || 0, "IDR")}</b>
                {rows.length ? ` · ${formatQty(rows.length)} channel` : ""}
              </span>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
