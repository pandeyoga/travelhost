import { Bus, IdCard, Wallet, Repeat } from "lucide-react";
import { formatCurrency, formatQty } from "@/utils/formatters";

const BUCKET_COLOR = { belum_jatuh_tempo: "#34C759", "0-30": "#007AFF", "31-60": "#FF9500", "61-90": "#FF6B22", "90+": "#FF3B30" };

function Card({ icon: Icon, title, color, action, children, loading, testId }) {
  return (
    <section className="section-card" data-testid={testId}>
      <div className="section-head">
        <div className="flex items-center gap-2"><Icon size={16} style={{ color }} /><h2>{title}</h2></div>
        {action}
      </div>
      <div className="section-body">
        {loading ? <div className="h-44 w-full animate-pulse rounded-[12px] bg-[#F0F1F4]" data-testid="bi-card-loading" /> : children}
      </div>
    </section>
  );
}

export function FleetCard({ fleet }) {
  const rows = fleet?.vehicles || [];
  return (
    <Card icon={Bus} title="Fleet ROI & Utilisasi" color="#34C759" testId="bi-fleet" loading={!fleet}
      action={<span className="text-[12px] text-[#6B6B73]">{formatQty(fleet?.active_units || 0)} aktif · {formatQty(fleet?.idle_units || 0)} idle</span>}>
      {rows.length === 0 ? (
        <p className="py-8 text-center text-[13px] text-[#6B6B73]" data-testid="bi-fleet-empty">Belum ada armada.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead><tr className="border-b border-[#EFF0F2] text-left text-[10.5px] uppercase tracking-wide text-[#8E8E93]">
              <th className="px-2 py-2">Armada</th><th className="px-2 py-2 text-right">Trip</th><th className="px-2 py-2 text-right">Pendapatan</th>
              <th className="px-2 py-2 text-right">Laba</th><th className="px-2 py-2 text-right">ROI</th></tr></thead>
            <tbody data-testid="bi-fleet-table">
              {rows.map((v) => (
                <tr key={v.vehicle_id} className="border-b border-[#F6F6F8] hover:bg-[#FAFAFB]" data-testid={`bi-fleet-row-${v.vehicle_id}`}>
                  <td className="px-2 py-2 font-medium text-[#1C1C1E]">{v.vehicle_name}{v.trips === 0 ? <span className="ml-1 rounded-full bg-[#F0F1F4] px-1.5 py-0.5 text-[9.5px] text-[#8E8E93]">idle</span> : null}</td>
                  <td className="px-2 py-2 text-right tabular-nums">{formatQty(v.trips)}</td>
                  <td className="px-2 py-2 text-right tabular-nums">{formatCurrency(v.revenue)}</td>
                  <td className="px-2 py-2 text-right tabular-nums" style={{ color: v.profit >= 0 ? "#127A36" : "#C0271E" }}>{formatCurrency(v.profit)}</td>
                  <td className="px-2 py-2 text-right tabular-nums font-semibold">{v.roi_pct != null ? `${v.roi_pct}%` : "\u2014"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

export function DriverCard({ drivers }) {
  const rows = drivers?.drivers || [];
  return (
    <Card icon={IdCard} title="Performa Driver" color="#30B0C7" testId="bi-drivers" loading={!drivers}>
      {rows.length === 0 ? (
        <p className="py-8 text-center text-[13px] text-[#6B6B73]" data-testid="bi-drivers-empty">Belum ada driver.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead><tr className="border-b border-[#EFF0F2] text-left text-[10.5px] uppercase tracking-wide text-[#8E8E93]">
              <th className="px-2 py-2">Driver</th><th className="px-2 py-2 text-right">Trip</th><th className="px-2 py-2 text-right">Selesai</th>
              <th className="px-2 py-2 text-right">Pendapatan</th><th className="px-2 py-2 text-right">Jarak</th></tr></thead>
            <tbody data-testid="bi-drivers-table">
              {rows.map((d) => (
                <tr key={d.driver_id} className="border-b border-[#F6F6F8] hover:bg-[#FAFAFB]" data-testid={`bi-driver-row-${d.driver_id}`}>
                  <td className="px-2 py-2 font-medium text-[#1C1C1E]">{d.driver_name}</td>
                  <td className="px-2 py-2 text-right tabular-nums">{formatQty(d.trips)}</td>
                  <td className="px-2 py-2 text-right tabular-nums">{formatQty(d.completed)} <span className="text-[#8E8E93]">({d.completion_rate}%)</span></td>
                  <td className="px-2 py-2 text-right tabular-nums">{formatCurrency(d.revenue)}</td>
                  <td className="px-2 py-2 text-right tabular-nums">{formatQty(d.distance_km)} km</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

export function ArAgingCard({ aging }) {
  const buckets = aging?.buckets || [];
  const total = aging?.total_outstanding || 0;
  const max = Math.max(1, ...buckets.map((b) => b.amount));
  const has = total > 0;
  return (
    <Card icon={Wallet} title="AR Aging (Piutang)" color="#FF9500" testId="bi-ar-aging" loading={!aging}
      action={<span className="text-[12px] font-semibold tabular-nums text-[#1C1C1E]">{formatCurrency(total)}</span>}>
      {!has ? (
        <p className="py-8 text-center text-[13px] text-[#6B6B73]" data-testid="bi-ar-empty">Tidak ada piutang berjalan.</p>
      ) : (
        <div className="space-y-3" data-testid="bi-ar-list">
          {buckets.map((b) => (
            <div key={b.bucket} data-testid={`bi-ar-row-${b.bucket}`}>
              <div className="mb-1 flex items-center justify-between text-[12.5px]">
                <span className="text-[#3C3C43]">{b.label} <span className="text-[#8E8E93]">· {formatQty(b.count)}</span></span>
                <span className="font-semibold tabular-nums text-[#1C1C1E]">{formatCurrency(b.amount)}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-[#F0F1F4]">
                <div className="h-full rounded-full" style={{ width: `${(b.amount / max) * 100}%`, background: BUCKET_COLOR[b.bucket] || "#007AFF" }} />
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

export function RetentionCard({ retention }) {
  const r = retention || {};
  const rfm = r.by_rfm || [];
  return (
    <Card icon={Repeat} title="Retensi & Cohort" color="#AF52DE" testId="bi-retention" loading={!retention}>
      <div className="grid grid-cols-3 gap-2">
        <Mini label="Repeat Rate" value={`${Math.round((r.repeat_rate || 0) * 100)}%`} tone="#AF52DE" testId="bi-ret-repeat" />
        <Mini label="Pelanggan Ulang" value={formatQty(r.returning_customers || 0)} tone="#34C759" testId="bi-ret-returning" />
        <Mini label="Sekali Pakai" value={formatQty(r.one_time_customers || 0)} tone="#FF9500" testId="bi-ret-onetime" />
      </div>
      <div className="mt-3">
        <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-[#8E8E93]">Segmen RFM</p>
        {rfm.length === 0 ? (
          <p className="text-[12.5px] text-[#6B6B73]">Belum ada segmen.</p>
        ) : (
          <div className="flex flex-wrap gap-1.5" data-testid="bi-ret-rfm">
            {rfm.map((s) => (
              <span key={s.segment} className="inline-flex items-center gap-1.5 rounded-full border border-[#EFF0F2] bg-[#FAFAFB] px-2.5 py-1 text-[11.5px]">
                <span className="text-[#3C3C43]">{s.segment}</span>
                <span className="font-bold tabular-nums text-[#1C1C1E]">{formatQty(s.count)}</span>
              </span>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}

function Mini({ label, value, tone, testId }) {
  return (
    <div className="rounded-[12px] border border-[#EFF0F2] bg-[#FAFAFB] p-3" data-testid={testId}>
      <p className="text-[11px] text-[#6B6B73]">{label}</p>
      <p className="mt-0.5 text-[20px] font-bold tabular-nums" style={{ color: tone, fontFamily: "Outfit, sans-serif" }}>{value}</p>
    </div>
  );
}
