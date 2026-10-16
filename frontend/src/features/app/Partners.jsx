import { useMemo, useState } from "react";
import { Handshake, Plus, Pencil, Trash2, Eye, Wallet, CheckCircle2, XCircle, Truck } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { useResource } from "@/hooks/useResource";
import { useAuth } from "@/context/AuthContext";
import DataTable from "@/components/shared/DataTable";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import { StatusPill } from "@/components/shared/StatusPill";
import ConfirmDialog from "@/components/shared/ConfirmDialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import PartnerFormDialog from "@/components/app/PartnerFormDialog";
import SubcharterFormDialog from "@/components/app/SubcharterFormDialog";
import SettlementDialog from "@/components/app/SettlementDialog";
import PartnerDetailDrawer from "@/components/app/PartnerDetailDrawer";
import { formatCurrency, formatDate, formatQty } from "@/utils/formatters";

const SC_TONE = { requested: "warning", confirmed: "info", settled: "success", cancelled: "neutral" };

function StatCard({ label, value, sub, testId }) {
  return (
    <div className="section-card p-4" data-testid={testId}>
      <p className="text-xs font-medium uppercase tracking-wide text-[#8A8A8E]">{label}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums text-[#1C1C1E]">{value}</p>
      {sub ? <p className="mt-0.5 text-xs text-[#8A8A8E]">{sub}</p> : null}
    </div>
  );
}

export default function Partners() {
  const { user } = useAuth();
  const canManage = user && (user.role === "owner" || user.role === "ops_admin");
  const { data: partners, loading: pLoad, error: pErr, reload: reloadP } = useResource("/partners");
  const { data: subs, loading: sLoad, error: sErr, reload: reloadS } = useResource("/subcharters");
  const pRows = Array.isArray(partners) ? partners : [];
  const sRows = Array.isArray(subs) ? subs : [];

  const [tab, setTab] = useState("partners");
  const [pForm, setPForm] = useState(false);
  const [pEditing, setPEditing] = useState(null);
  const [pDel, setPDel] = useState(null);
  const [detail, setDetail] = useState(null);
  const [settleTarget, setSettleTarget] = useState(null);
  const [scForm, setScForm] = useState(false);
  const [scEditing, setScEditing] = useState(null);
  const [scCancel, setScCancel] = useState(null);
  const [scDel, setScDel] = useState(null);
  const [busy, setBusy] = useState(false);

  const reloadAll = () => { reloadP(); reloadS(); };

  const totals = useMemo(() => {
    const outstanding = pRows.reduce((a, p) => a + (Number(p.ap_outstanding) || 0), 0);
    const activeSc = sRows.filter((s) => ["requested", "confirmed"].includes(s.status)).length;
    return { outstanding, activeSc };
  }, [pRows, sRows]);

  const doDeletePartner = async () => {
    if (!pDel) return;
    setBusy(true);
    try {
      await apiClient.delete(`/partners/${pDel.id}`);
      toast.success("Mitra dihapus");
      setPDel(null); reloadAll();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menghapus mitra"); }
    finally { setBusy(false); }
  };

  const confirmSc = async (sc) => {
    try {
      await apiClient.post(`/subcharters/${sc.id}/confirm`);
      toast.success(`Order ${sc.code} dikonfirmasi — WA terkirim ke mitra & COGS dibukukan`);
      reloadAll();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal konfirmasi order"); }
  };
  const settleSc = async (sc) => {
    try {
      await apiClient.post(`/subcharters/${sc.id}/settle`);
      toast.success(`Order ${sc.code} ditandai lunas ke mitra`);
      reloadAll();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal melunasi order"); }
  };
  const doCancelSc = async () => {
    if (!scCancel) return;
    setBusy(true);
    try {
      await apiClient.post(`/subcharters/${scCancel.id}/cancel`);
      toast.success(`Order ${scCancel.code} dibatalkan`);
      setScCancel(null); reloadAll();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal membatalkan order"); }
    finally { setBusy(false); }
  };

  const doDeleteSc = async () => {
    if (!scDel) return;
    setBusy(true);
    try {
      await apiClient.delete(`/subcharters/${scDel.id}`);
      toast.success(`Order ${scDel.code} dihapus`);
      setScDel(null); reloadAll();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menghapus order"); }
    finally { setBusy(false); }
  };

  const partnerCols = [
    { key: "name", label: "Mitra", render: (r) => (
      <div><span className="font-semibold text-[#1C1C1E]">{r.name}</span>
        <p className="text-xs text-[#8A8A8E]">{r.pic || "—"}{r.city ? ` · ${r.city}` : ""}</p></div>
    ) },
    { key: "phone", label: "Telepon", mono: true, render: (r) => r.phone || "—" },
    { key: "vehicle_count", label: "Unit", align: "right", mono: true, render: (r) => formatQty(r.vehicle_count) },
    { key: "ap_outstanding", label: "Utang (AP)", align: "right", mono: true, render: (r) => (
      <span className={Number(r.ap_outstanding) > 0 ? "font-semibold text-[#A8221A]" : "text-[#34C759]"}>{formatCurrency(r.ap_outstanding)}</span>
    ) },
    { key: "rating", label: "Rating", align: "right", mono: true, render: (r) => `${formatQty(r.rating)} ★` },
  ];
  partnerCols.push({
    key: "aksi", label: "Aksi", align: "right",
    render: (r) => (
      <div className="flex justify-end gap-1.5">
        <button className="icon-button !h-8 !w-8" title="Detail & riwayat" onClick={(e) => { e.stopPropagation(); setDetail(r); }} data-testid={`partner-detail-${r.id}`}><Eye size={14} /></button>
        {canManage && <button className="icon-button !h-8 !w-8" title="Catat pelunasan" onClick={(e) => { e.stopPropagation(); setSettleTarget(r); }} data-testid={`partner-settle-${r.id}`}><Wallet size={14} /></button>}
        {canManage && <button className="icon-button !h-8 !w-8" title="Edit" onClick={(e) => { e.stopPropagation(); setPEditing(r); setPForm(true); }} data-testid={`partner-edit-${r.id}`}><Pencil size={14} /></button>}
        {canManage && <button className="icon-button !h-8 !w-8 !text-[#A8221A]" title="Hapus" onClick={(e) => { e.stopPropagation(); setPDel(r); }} data-testid={`partner-delete-${r.id}`}><Trash2 size={14} /></button>}
      </div>
    ),
  });

  const scCols = [
    { key: "code", label: "Kode", mono: true, render: (r) => <span className="font-semibold text-[#1C1C1E]">{r.code}</span> },
    { key: "partner_name", label: "Mitra" },
    { key: "vehicle_label", label: "Unit", render: (r) => r.vehicle_label || "—" },
    { key: "booking_code", label: "Booking", mono: true, render: (r) => r.booking_code || "—" },
    { key: "start_datetime", label: "Periode", render: (r) => `${formatDate(r.start_datetime)} → ${formatDate(r.end_datetime)}` },
    { key: "cost", label: "Biaya Mitra", align: "right", mono: true, render: (r) => formatCurrency(r.cost) },
    { key: "status", label: "Status", render: (r) => <StatusPill value={r.status} tone={SC_TONE[r.status] || "neutral"} /> },
  ];
  if (canManage) {
    scCols.push({
      key: "aksi", label: "Aksi", align: "right",
      render: (r) => (
        <div className="flex justify-end gap-1.5">
          {r.status === "requested" && <button className="icon-button !h-8 !w-8 !text-[#007AFF]" title="Konfirmasi" onClick={(e) => { e.stopPropagation(); confirmSc(r); }} data-testid={`sc-confirm-${r.id}`}><CheckCircle2 size={14} /></button>}
          {r.status === "requested" && <button className="icon-button !h-8 !w-8" title="Edit" onClick={(e) => { e.stopPropagation(); setScEditing(r); setScForm(true); }} data-testid={`sc-edit-${r.id}`}><Pencil size={14} /></button>}
          {r.status === "confirmed" && <button className="icon-button !h-8 !w-8 !text-[#34C759]" title="Tandai lunas" onClick={(e) => { e.stopPropagation(); settleSc(r); }} data-testid={`sc-settle-${r.id}`}><Wallet size={14} /></button>}
          {["requested", "confirmed"].includes(r.status) && <button className="icon-button !h-8 !w-8 !text-[#A8221A]" title="Batalkan" onClick={(e) => { e.stopPropagation(); setScCancel(r); }} data-testid={`sc-cancel-${r.id}`}><XCircle size={14} /></button>}
          {["requested", "cancelled"].includes(r.status) && <button className="icon-button !h-8 !w-8 !text-[#A8221A]" title="Hapus" onClick={(e) => { e.stopPropagation(); setScDel(r); }} data-testid={`sc-delete-${r.id}`}><Trash2 size={14} /></button>}
        </div>
      ),
    });
  }

  const addPartnerBtn = canManage ? (
    <button className="primary-button" onClick={() => { setPEditing(null); setPForm(true); }} data-testid="partner-add-button"><Plus size={14} /> Tambah Mitra</button>
  ) : null;
  const addScBtn = canManage ? (
    <button className="primary-button" onClick={() => { setScEditing(null); setScForm(true); }} data-testid="subcharter-add-button"><Plus size={14} /> Buat Order Sub-charter</button>
  ) : null;

  return (
    <div className="space-y-4" data-testid="partners-page">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatCard label="Total Utang ke Mitra" value={formatCurrency(totals.outstanding)} sub="Akumulasi AP outstanding" testId="stat-ap-outstanding" />
        <StatCard label="Order Aktif" value={formatQty(totals.activeSc)} sub="requested + confirmed" testId="stat-active-sc" />
        <StatCard label="Mitra Terdaftar" value={formatQty(pRows.length)} sub="Travel partner" testId="stat-partner-count" />
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList data-testid="partners-tabs">
          <TabsTrigger value="partners" data-testid="tab-partners"><Handshake size={14} className="mr-1.5" /> Mitra & Utang</TabsTrigger>
          <TabsTrigger value="subcharters" data-testid="tab-subcharters"><Truck size={14} className="mr-1.5" /> Order Sub-charter</TabsTrigger>
        </TabsList>

        <TabsContent value="partners" className="mt-4">
          {pLoad ? <LoadingState testId="partners-loading" /> : pErr ? <ErrorState message={pErr} onRetry={reloadP} /> : pRows.length === 0 ? (
            <div className="space-y-3"><div className="flex justify-end">{addPartnerBtn}</div>
              <EmptyState title="Belum ada mitra" description="Daftarkan travel mitra untuk mulai pinjam armada." action={addPartnerBtn} testId="partners-empty" /></div>
          ) : (
            <DataTable title="Travel Mitra" icon={Handshake} columns={partnerCols} rows={pRows} actions={addPartnerBtn} onRowClick={setDetail} footer={`${formatQty(pRows.length)} mitra · total utang ${formatCurrency(totals.outstanding)}`} testId="partners-table" />
          )}
        </TabsContent>

        <TabsContent value="subcharters" className="mt-4">
          {sLoad ? <LoadingState testId="subcharters-loading" /> : sErr ? <ErrorState message={sErr} onRetry={reloadS} /> : sRows.length === 0 ? (
            <div className="space-y-3"><div className="flex justify-end">{addScBtn}</div>
              <EmptyState title="Belum ada order sub-charter" description="Buat order saat armada sendiri penuh dan perlu pinjam unit mitra." action={addScBtn} testId="subcharters-empty" /></div>
          ) : (
            <DataTable title="Order Sub-charter" icon={Truck} columns={scCols} rows={sRows} actions={addScBtn} footer={`${formatQty(sRows.length)} order`} testId="subcharters-table" />
          )}
        </TabsContent>
      </Tabs>

      <PartnerFormDialog open={pForm} onOpenChange={setPForm} initial={pEditing} onSaved={reloadAll} />
      <SubcharterFormDialog open={scForm} onOpenChange={setScForm} initial={scEditing} onSaved={reloadAll} />
      <SettlementDialog open={Boolean(settleTarget)} onOpenChange={(v) => !v && setSettleTarget(null)} partner={settleTarget} onSaved={reloadAll} />
      <PartnerDetailDrawer open={Boolean(detail)} partner={detail} onOpenChange={(v) => !v && setDetail(null)} />
      <ConfirmDialog open={Boolean(pDel)} onOpenChange={(v) => !v && setPDel(null)} title="Hapus mitra?" description={pDel ? `"${pDel.name}" akan dihapus permanen.` : ""} busy={busy} onConfirm={doDeletePartner} testId="partner-delete-confirm" />
      <ConfirmDialog open={Boolean(scCancel)} onOpenChange={(v) => !v && setScCancel(null)} title="Batalkan order?" description={scCancel ? `Order ${scCancel.code} akan dibatalkan. Bila sudah dikonfirmasi, COGS akan dibatalkan juga.` : ""} confirmLabel="Batalkan" busy={busy} onConfirm={doCancelSc} testId="sc-cancel-confirm" />
      <ConfirmDialog open={Boolean(scDel)} onOpenChange={(v) => !v && setScDel(null)} title="Hapus order sub-charter?" description={scDel ? `Order ${scDel.code} (${scDel.partner_name}) akan dihapus permanen.` : ""} busy={busy} onConfirm={doDeleteSc} testId="sc-delete-confirm" />
    </div>
  );
}
