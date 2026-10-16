import { useCallback, useEffect, useState } from "react";
import { Route, CheckCircle2, Gauge, Wallet, Star, Phone, Coins, Plus, Settings2, FileText } from "lucide-react";
import apiClient from "@/services/apiClient";
import { useAuth } from "@/context/AuthContext";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from "@/components/ui/sheet";
import { formatCurrency, formatDate, formatQty } from "@/utils/formatters";
import DriverCompDialog from "@/components/app/DriverCompDialog";
import PayoutFormDialog from "@/components/app/PayoutFormDialog";
import PayoutDetailDialog from "@/components/app/PayoutDetailDialog";

function Stat({ icon: Icon, label, value, tone = "#007AFF" }) {
  return (
    <div className="rounded-[12px] border border-[#EFF0F2] bg-white p-3">
      <div className="flex items-center gap-1.5 text-[11px] font-semibold text-[#6B6B73]"><Icon size={13} style={{ color: tone }} /> {label}</div>
      <div className="mt-0.5 text-[18px] font-bold tabular-nums text-[#1C1C1E]" style={{ fontFamily: "Outfit, sans-serif" }}>{value}</div>
    </div>
  );
}

const TONE = { completed: "success", on_trip: "info", to_pickup: "warning", standby: "neutral" };
const PAYOUT_STATUS = { draft: { l: "Draft", tone: "neutral" }, approved: { l: "Disetujui", tone: "info" }, paid: { l: "Dibayar", tone: "success" } };

function CompLine({ label, value, active }) {
  return (
    <div className="flex items-center justify-between rounded-[10px] border border-[#F2F2F5] px-3 py-2">
      <span className="flex items-center gap-2 text-[12.5px] text-[#3C3C43]">
        <span className={`h-1.5 w-1.5 rounded-full ${active ? "bg-[#34C759]" : "bg-[#D1D1D6]"}`} /> {label}
      </span>
      <span className={`tabular-nums text-[13px] font-semibold ${active ? "text-[#1C1C1E]" : "text-[#C7C7CC]"}`}>{value}</span>
    </div>
  );
}

export default function DriverDetailDrawer({ open, driver, onOpenChange }) {
  const { user } = useAuth();
  const canManage = user && (user.role === "owner" || user.role === "ops_admin");
  const [tab, setTab] = useState("performance");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [comp, setComp] = useState(null);
  const [payouts, setPayouts] = useState([]);
  const [compLoading, setCompLoading] = useState(false);
  const [compOpen, setCompOpen] = useState(false);
  const [genOpen, setGenOpen] = useState(false);
  const [detailId, setDetailId] = useState(null);

  useEffect(() => { if (open) setTab("performance"); }, [open, driver?.id]);
  useEffect(() => { setComp(null); setPayouts([]); }, [driver?.id]);

  useEffect(() => {
    if (!open || !driver?.id) return;
    setLoading(true); setData(null);
    apiClient.get(`/drivers/${driver.id}/performance`)
      .then((r) => setData(r.data))
      .catch(() => setData({ stats: {}, trips: [] }))
      .finally(() => setLoading(false));
  }, [open, driver]);

  const loadComp = useCallback(async () => {
    if (!driver?.id) return;
    setCompLoading(true);
    try {
      const [c, p] = await Promise.all([
        apiClient.get(`/drivers/${driver.id}/compensation`),
        apiClient.get("/payroll/payouts", { params: { driver_id: driver.id } }),
      ]);
      setComp(c.data?.comp || {});
      setPayouts(Array.isArray(p.data) ? p.data : []);
    } catch (e) {
      setComp({}); setPayouts([]);
    } finally { setCompLoading(false); }
  }, [driver]);

  useEffect(() => {
    if (open && canManage && tab === "compensation" && comp === null) loadComp();
  }, [open, canManage, tab, comp, loadComp]);

  const s = data?.stats || {};
  const trips = data?.trips || [];
  const c = comp || {};

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-xl" data-testid="driver-detail-drawer">
        <SheetHeader>
          <SheetTitle>{driver?.name || "Driver"}</SheetTitle>
          <SheetDescription className="flex flex-wrap items-center gap-3 text-[12.5px]">
            {driver?.phone ? <span className="flex items-center gap-1"><Phone size={12} /> {driver.phone}</span> : null}
            {driver?.rating > 0 ? <span className="flex items-center gap-1"><Star size={12} /> {formatQty(driver.rating)}</span> : null}
          </SheetDescription>
        </SheetHeader>

        <div className="tab-bar mt-4" data-testid="dd-tabs">
          <button className={`tab-button ${tab === "performance" ? "active" : ""}`} onClick={() => setTab("performance")} data-testid="dd-tab-performance">
            <Route size={14} /> Kinerja
          </button>
          {canManage ? (
            <button className={`tab-button ${tab === "compensation" ? "active" : ""}`} onClick={() => setTab("compensation")} data-testid="dd-tab-compensation">
              <Coins size={14} /> Kompensasi
            </button>
          ) : null}
        </div>

        {/* ---- TAB: Kinerja ---- */}
        {tab === "performance" ? (
          loading ? (
            <div className="py-10 text-center text-[13px] text-[#8E8E93]" data-testid="dd-loading">Memuat kinerja…</div>
          ) : (
            <div className="mt-4 space-y-4">
              <div className="grid grid-cols-2 gap-2.5" data-testid="dd-stats">
                <Stat icon={Route} label="Total Trip" value={formatQty(s.total_trips || 0)} />
                <Stat icon={CheckCircle2} label="Selesai" value={`${formatQty(s.completed || 0)} (${formatQty(s.completion_rate || 0)}%)`} tone="#34C759" />
                <Stat icon={Gauge} label="Total KM" value={`${formatQty(s.total_km || 0)} km`} tone="#FF9500" />
                <Stat icon={Wallet} label="Total Revenue" value={formatCurrency(s.total_revenue || 0)} tone="#5856D6" />
              </div>
              <div>
                <h3 className="mb-2 text-[12px] font-bold uppercase tracking-wide text-[#6B6B73]">Riwayat Trip</h3>
                {trips.length === 0 ? (
                  <div className="rounded-[12px] border border-dashed border-[#E2E3E6] bg-[#FAFAFB] p-6 text-center text-[13px] text-[#8E8E93]" data-testid="dd-empty">Belum ada trip.</div>
                ) : (
                  <div className="overflow-hidden rounded-[12px] border border-[#EFF0F2]" data-testid="dd-trips">
                    <table className="w-full text-[12px]">
                      <thead className="bg-[#FAFAFB] text-[10px] uppercase tracking-wide text-[#6B6B73]">
                        <tr><th className="px-3 py-2 text-left">Trip</th><th className="px-3 py-2 text-left">Armada</th><th className="px-3 py-2 text-right">KM</th><th className="px-3 py-2 text-right">Revenue</th><th className="px-3 py-2 text-left">Tanggal</th></tr>
                      </thead>
                      <tbody>
                        {trips.map((t) => (
                          <tr key={t.id} className="border-t border-[#F2F2F5]">
                            <td className="px-3 py-2"><div className="font-semibold text-[#1C1C1E]">{t.code || "-"}</div><span className={`status-pill tone-${TONE[t.status] || "neutral"}`}>{t.status}</span></td>
                            <td className="px-3 py-2 text-[#3A3A3C]">{t.vehicle_name || "-"}</td>
                            <td className="px-3 py-2 text-right tabular-nums">{formatQty(t.distance_km || 0)}</td>
                            <td className="px-3 py-2 text-right tabular-nums">{formatCurrency(t.revenue || 0)}</td>
                            <td className="px-3 py-2 tabular-nums text-[#6B6B73]">{formatDate(t.end_at || t.start_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )
        ) : null}

        {/* ---- TAB: Kompensasi ---- */}
        {tab === "compensation" && canManage ? (
          compLoading ? (
            <div className="py-10 text-center text-[13px] text-[#8E8E93]" data-testid="dd-comp-loading">Memuat kompensasi…</div>
          ) : (
            <div className="mt-4 space-y-4" data-testid="dd-comp">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-[12px] font-bold uppercase tracking-wide text-[#6B6B73]">Skema Kompensasi</h3>
                <div className="flex gap-2">
                  <button className="secondary-button !h-8" onClick={() => setCompOpen(true)} data-testid="dd-comp-edit"><Settings2 size={13} /> Atur</button>
                  <button className="primary-button !h-8" onClick={() => setGenOpen(true)} data-testid="dd-comp-generate"><Plus size={13} /> Payout</button>
                </div>
              </div>
              <div className="space-y-1.5">
                <CompLine label="Gaji Pokok (bulanan)" value={formatCurrency(c.base_salary_monthly || 0)} active={c.enable_base !== false} />
                <CompLine label="Komisi per Trip" value={formatCurrency(c.commission_per_trip || 0)} active={Boolean(c.enable_commission_trip)} />
                <CompLine label={`Komisi % Revenue (${c.revenue_base === "booking" ? "booking" : "trip"})`} value={`${formatQty(c.commission_pct_revenue || 0)}%`} active={Boolean(c.enable_commission_pct)} />
                <CompLine label="Uang Jalan per KM" value={formatCurrency(c.allowance_per_km || 0)} active={Boolean(c.enable_allowance_km)} />
              </div>

              <div>
                <h3 className="mb-2 text-[12px] font-bold uppercase tracking-wide text-[#6B6B73]">Riwayat Payout</h3>
                {payouts.length === 0 ? (
                  <div className="rounded-[12px] border border-dashed border-[#E2E3E6] bg-[#FAFAFB] p-6 text-center text-[13px] text-[#8E8E93]" data-testid="dd-payouts-empty">Belum ada payout.</div>
                ) : (
                  <div className="space-y-2" data-testid="dd-payouts">
                    {payouts.map((p) => {
                      const st = PAYOUT_STATUS[p.status] || { l: p.status, tone: "neutral" };
                      return (
                        <button key={p.id} className="flex w-full items-center justify-between rounded-[10px] border border-[#EFF0F2] bg-white px-3 py-2.5 text-left hover:bg-[#FAFAFB]" onClick={() => setDetailId(p.id)} data-testid={`dd-payout-${p.id}`}>
                          <div>
                            <p className="text-[12.5px] font-semibold text-[#1C1C1E]">{formatDate(p.period_start)} → {formatDate(p.period_end)}</p>
                            <p className="text-[11px] text-[#8E8E93]">{formatQty(p.trips_count || 0)} trip · {formatQty(p.total_km || 0)} km</p>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-[13px] font-bold tabular-nums text-[#1C1C1E]">{formatCurrency(p.total)}</span>
                            <span className={`status-pill tone-${st.tone}`}>{st.l}</span>
                            <FileText size={14} className="text-[#8E8E93]" />
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )
        ) : null}
      </SheetContent>

      <DriverCompDialog open={compOpen} onOpenChange={setCompOpen} driverId={driver?.id} driverName={driver?.name} onSaved={loadComp} />
      <PayoutFormDialog open={genOpen} onOpenChange={setGenOpen} presetDriverId={driver?.id} onSaved={(id) => { loadComp(); if (id) setDetailId(id); }} />
      <PayoutDetailDialog payoutId={detailId} onOpenChange={(v) => { if (!v) setDetailId(null); }} onChanged={loadComp} canManage={canManage} />
    </Sheet>
  );
}
