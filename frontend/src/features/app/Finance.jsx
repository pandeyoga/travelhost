import { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { toast } from "sonner";
import {
  Banknote, Wallet, TrendingUp, Percent, Plus, FileText, Receipt, Download,
  PieChart as PieIcon, Calendar, FileSpreadsheet, Wrench, Truck,
  GitCompareArrows, Waves, Send, Loader2, BellRing, Users, Pencil, Trash2,
} from "lucide-react";
import apiClient from "@/services/apiClient";
import { LoadingState, EmptyState, ErrorState } from "@/components/shared/DataStates";
import { PaymentPill } from "@/components/shared/StatusPill";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatCurrency, formatDate } from "@/utils/formatters";
import ExpenseFormDialog from "@/components/app/ExpenseFormDialog";
import ConfirmDialog from "@/components/shared/ConfirmDialog";
import InvoiceFormDialog from "@/components/app/InvoiceFormDialog";
import InvoiceEditDialog from "@/components/app/InvoiceEditDialog";
import PaymentDialog from "@/components/app/PaymentDialog";
import FinanceReconciliation from "@/components/app/FinanceReconciliation";
import FinanceCashflow from "@/components/app/FinanceCashflow";
import PayrollManager from "@/components/app/PayrollManager";
import DriverWithdrawalsPanel from "@/components/app/DriverWithdrawalsPanel";
import ReceiptsPanel, { openPdf } from "@/components/app/ReceiptsPanel";
import { Eye, ReceiptText } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { canAccess } from "@/config/navigationConfig";

const TABS = [
  ["pl", "Laba-Rugi", TrendingUp],
  ["expenses", "Pengeluaran", Receipt],
  ["invoices", "Invoice", FileText],
  ["receipts", "Kwitansi", ReceiptText],
  ["ar", "Piutang", Wallet],
  ["recon", "Rekonsiliasi", GitCompareArrows],
  ["cashflow", "Arus Kas", Waves],
  ["payroll", "Payroll", Users],
  ["fees", "Fee Driver", Banknote],
];
const CAT_LABEL = { bbm: "BBM / Solar", tol: "Tol & Parkir", uang_jalan: "Uang Jalan", gaji_driver: "Gaji/Komisi Driver", other: "Lainnya" };
const INV_STATUS = {
  draft: { l: "Draft", tone: "neutral" },
  sent: { l: "Terkirim", tone: "info" },
  partial: { l: "Sebagian", tone: "warning" },
  paid: { l: "Lunas", tone: "success" },
  void: { l: "Batal", tone: "danger" },
};
const KIND_TONE = { dp: "tone-warning", settlement: "tone-info", full: "tone-neutral" };

function lastMonths(n = 6) {
  const out = [];
  const d = new Date();
  for (let i = 0; i < n; i += 1) {
    const dt = new Date(d.getFullYear(), d.getMonth() - i, 1);
    const key = `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}`;
    out.push([key, dt.toLocaleDateString("id-ID", { month: "long", year: "numeric" })]);
  }
  return out;
}

function daysSince(value) {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  return Math.floor((Date.now() - d.getTime()) / 86400000);
}

function Kpi({ icon: Icon, label, value, color, isPct }) {
  return (
    <div className="kpi-card" data-testid={`fin-kpi-${label}`}>
      <div className="kpi-top">
        <span className="kpi-icon" style={{ background: `${color}18` }}><Icon size={16} style={{ color }} /></span>
        <span className="kpi-label">{label}</span>
      </div>
      <p className="kpi-value tabular-nums">{isPct ? `${value || 0}%` : formatCurrency(value || 0)}</p>
    </div>
  );
}

async function downloadFile(url, filename) {
  try {
    const res = await apiClient.get(url, { responseType: "blob" });
    const blobUrl = window.URL.createObjectURL(res.data);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(blobUrl);
  } catch (e) {
    toast.error("Gagal mengunduh file");
  }
}

export default function Finance() {
  const { user } = useAuth();
  const months = lastMonths(6);
  const [tab, setTab] = useState("pl");
  const [period, setPeriod] = useState(months[0][0]);
  const [summary, setSummary] = useState(null);
  const [exporting, setExporting] = useState("");

  const loadSummary = useCallback(() => {
    apiClient.get(`/finance/summary?period=${period}`).then((r) => setSummary(r.data)).catch(() => setSummary(null));
  }, [period]);
  useEffect(() => { loadSummary(); }, [loadSummary]);

  const exportReport = async (format) => {
    setExporting(format);
    const ext = format === "pdf" ? "pdf" : "xlsx";
    await downloadFile(`/finance/export?format=${format}&period=${period}`, `laporan-keuangan-${period}.${ext}`);
    setExporting("");
  };

  // RBAC: hanya owner/ops_admin (section 'finance') boleh mengakses halaman Keuangan (termasuk Payroll).
  if (user && !canAccess(user.role, "finance")) {
    return <Navigate to="/app/dashboard" replace />;
  }

  const s = summary || {};

  return (
    <div className="space-y-4" data-testid="finance-page">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="grid flex-1 grid-cols-2 gap-3 sm:grid-cols-4">
          <Kpi icon={Banknote} label="Pemasukan" value={s.revenue} color="#0058CC" />
          <Kpi icon={Receipt} label="Pengeluaran" value={s.expenses} color="#FF3B30" />
          <Kpi icon={TrendingUp} label="Laba Bersih" value={s.profit} color="#34C759" />
          <Kpi icon={Wallet} label="Piutang (AR)" value={s.outstanding_ar} color="#FF9500" />
        </div>
        <div className="flex items-center gap-2">
          <Calendar size={15} className="text-[#8E8E93]" />
          <Select value={period} onValueChange={setPeriod}>
            <SelectTrigger className="w-[160px]" data-testid="finance-period"><SelectValue /></SelectTrigger>
            <SelectContent>{months.map(([k, l]) => <SelectItem key={k} value={k}>{l}</SelectItem>)}</SelectContent>
          </Select>
          <button className="secondary-button" disabled={Boolean(exporting)} onClick={() => exportReport("pdf")} data-testid="finance-export-pdf">
            {exporting === "pdf" ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />} PDF
          </button>
          <button className="secondary-button" disabled={Boolean(exporting)} onClick={() => exportReport("excel")} data-testid="finance-export-excel">
            {exporting === "excel" ? <Loader2 size={14} className="animate-spin" /> : <FileSpreadsheet size={14} />} Excel
          </button>
        </div>
      </div>

      <div className="tab-bar">
        {TABS.map(([k, l, Icon]) => (
          <button key={k} className={`tab-button ${tab === k ? "active" : ""}`} onClick={() => setTab(k)} data-testid={`tab-finance-${k}`}>
            <Icon size={14} /> {l}
          </button>
        ))}
      </div>

      {tab === "pl" && <ProfitLoss period={period} />}
      {tab === "expenses" && <Expenses onChanged={loadSummary} />}
      {tab === "invoices" && <Invoices onChanged={loadSummary} />}
      {tab === "receipts" && <ReceiptsPanel />}
      {tab === "ar" && <Receivables onChanged={loadSummary} />}
      {tab === "recon" && <FinanceReconciliation onChanged={loadSummary} />}
      {tab === "cashflow" && <FinanceCashflow />}
      {tab === "payroll" && <PayrollManager />}
      {tab === "fees" && <DriverWithdrawalsPanel />}
    </div>
  );
}

function ProfitLoss({ period }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get(`/finance/pl-full?period=${period}`)
      .then((r) => { setData(r.data); setError(null); })
      .catch(() => setError("Gagal memuat laba-rugi"))
      .finally(() => setLoading(false));
  }, [period]);
  useEffect(() => { load(); }, [load]);

  if (loading) return <LoadingState rows={3} testId="pl-loading" />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!data) return <EmptyState title="Belum ada data" description="Laba-rugi belum tersedia untuk periode ini." testId="pl-empty" />;

  const cats = data.expense_by_category || [];
  const maxCat = Math.max(1, ...cats.map((c) => c.amount));
  const units = Array.isArray(data.per_unit) ? data.per_unit : [];
  const profitPositive = (data.profit || 0) >= 0;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2" data-testid="pl-panel">
      <section className="section-card">
        <div className="section-head"><div className="flex items-center gap-2"><TrendingUp size={16} className="text-[#34C759]" /><h2>Ringkasan Laba-Rugi</h2></div></div>
        <div className="section-body space-y-3">
          {[
            ["Pemasukan (cash-in)", data.revenue, "#0058CC"],
            ["Biaya Operasional", data.operational_expenses, "#FF3B30"],
            ["Biaya Perawatan", data.maintenance_cost, "#FF9500"],
            ["Total Biaya", data.total_cost, "#C0271E"],
          ].map(([l, v, c]) => (
            <div key={l} className="flex items-center justify-between rounded-[10px] border border-[#F2F2F5] px-3 py-2.5">
              <span className="text-[13px] text-[#3C3C43]">{l}</span>
              <span className="text-[14px] font-bold tabular-nums" style={{ color: c }}>{formatCurrency(v)}</span>
            </div>
          ))}
          <div className="flex items-center justify-between rounded-[10px] px-3 py-3" style={{ background: profitPositive ? "rgba(52,199,89,0.10)" : "rgba(255,59,48,0.10)" }}>
            <span className="text-[13px] font-semibold" style={{ color: profitPositive ? "#126E2C" : "#A8221A" }}>Laba Bersih</span>
            <span className="text-[18px] font-bold tabular-nums" style={{ color: profitPositive ? "#126E2C" : "#A8221A" }}>{formatCurrency(data.profit)}</span>
          </div>
          <div className="flex items-center justify-between px-1 text-[12.5px] text-[#6B6B73]">
            <span className="flex items-center gap-1"><Percent size={13} /> Margin</span>
            <span className="font-semibold tabular-nums text-[#1C1C1E]">{data.margin || 0}%</span>
          </div>
        </div>
      </section>

      <section className="section-card">
        <div className="section-head"><div className="flex items-center gap-2"><PieIcon size={16} className="text-[#007AFF]" /><h2>Pengeluaran per Kategori</h2></div></div>
        <div className="section-body">
          {(data.operational_expenses || 0) === 0 ? (
            <p className="py-8 text-center text-[13px] text-[#6B6B73]" data-testid="pl-cat-empty">Belum ada pengeluaran pada periode ini.</p>
          ) : (
            <div className="space-y-3" data-testid="pl-cat-list">
              {cats.map((c) => (
                <div key={c.category}>
                  <div className="mb-1 flex items-center justify-between text-[12.5px]">
                    <span className="text-[#3C3C43]">{CAT_LABEL[c.category] || c.category}</span>
                    <span className="font-semibold tabular-nums text-[#1C1C1E]">{formatCurrency(c.amount)}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-[#F0F1F4]">
                    <div className="h-full rounded-full bg-[#007AFF]" style={{ width: `${(c.amount / maxCat) * 100}%` }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="section-card lg:col-span-2">
        <div className="section-head"><div className="flex items-center gap-2"><Truck size={16} className="text-[#AF52DE]" /><h2>Laba-Rugi per Unit (incl. Perawatan)</h2></div></div>
        <div className="overflow-x-auto">
          {units.length === 0 ? (
            <p className="py-8 text-center text-[13px] text-[#6B6B73]" data-testid="pl-unit-empty">Belum ada armada tercatat.</p>
          ) : (
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="border-b border-[#EFF0F2] text-left text-[10.5px] uppercase tracking-wide text-[#8E8E93]">
                  <th className="px-4 py-2.5">Armada</th>
                  <th className="px-3 py-2.5 text-right">Pendapatan</th>
                  <th className="px-3 py-2.5 text-right">Operasional</th>
                  <th className="px-3 py-2.5 text-right"><span className="inline-flex items-center gap-1"><Wrench size={11} /> Perawatan</span></th>
                  <th className="px-3 py-2.5 text-right">Laba</th>
                </tr>
              </thead>
              <tbody data-testid="pl-unit-list">
                {units.map((u) => (
                  <tr key={u.vehicle_id} className="border-b border-[#F6F6F8] hover:bg-[#FAFAFB]" data-testid={`pl-unit-${u.vehicle_id}`}>
                    <td className="px-4 py-3 font-semibold text-[#1C1C1E]">{u.vehicle_name}</td>
                    <td className="px-3 py-3 text-right tabular-nums text-[#0058CC]">{formatCurrency(u.revenue)}</td>
                    <td className="px-3 py-3 text-right tabular-nums text-[#FF3B30]">{formatCurrency(u.operational_expenses)}</td>
                    <td className="px-3 py-3 text-right tabular-nums text-[#FF9500]">{formatCurrency(u.maintenance)}</td>
                    <td className="px-3 py-3 text-right tabular-nums font-bold" style={{ color: u.profit >= 0 ? "#126E2C" : "#A8221A" }}>{formatCurrency(u.profit)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </div>
  );
}

function Expenses({ onChanged }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [delTarget, setDelTarget] = useState(null);
  const [busy, setBusy] = useState(false);

  const doDelete = async () => {
    if (!delTarget) return;
    setBusy(true);
    try {
      await apiClient.delete(`/expenses/${delTarget.id}`);
      toast.success("Pengeluaran dihapus");
      setDelTarget(null); load(); onChanged && onChanged();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menghapus pengeluaran"); }
    finally { setBusy(false); }
  };

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get("/expenses")
      .then((r) => { setRows(Array.isArray(r.data) ? r.data : []); setError(null); })
      .catch(() => setError("Gagal memuat pengeluaran"))
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  const addBtn = (
    <button className="primary-button" onClick={() => { setEditing(null); setOpen(true); }} data-testid="expense-add"><Plus size={14} /> Tambah Pengeluaran</button>
  );

  return (
    <div className="space-y-3" data-testid="expenses-panel">
      <div className="flex justify-end">{addBtn}</div>
      {loading ? <LoadingState testId="expenses-loading" />
        : error ? <ErrorState message={error} onRetry={load} />
        : rows.length === 0 ? <EmptyState title="Belum ada pengeluaran" description="Catat BBM, tol, uang jalan, dll." testId="expenses-empty" action={addBtn} />
        : (
          <section className="section-card">
            <div className="section-head"><div className="flex items-center gap-2"><Receipt size={16} className="text-[#FF3B30]" /><h2>Daftar Pengeluaran</h2></div></div>
            <div className="divide-y divide-[#F2F2F5]" data-testid="expenses-list">
              {rows.map((e) => (
                <div key={e.id} className="flex items-center justify-between gap-3 px-4 py-3" data-testid={`expense-${e.id}`}>
                  <div className="min-w-0">
                    <p className="text-[13px] font-semibold text-[#1C1C1E]">{CAT_LABEL[e.category] || e.category}{e.booking_code ? ` · ${e.booking_code}` : ""}</p>
                    <p className="truncate text-[11.5px] text-[#6B6B73]">{e.note || "-"} · {formatDate(e.created_at)}</p>
                  </div>
                  <div className="flex flex-shrink-0 items-center gap-2">
                    <span className="text-[14px] font-bold tabular-nums text-[#FF3B30]">-{formatCurrency(e.amount)}</span>
                    <button className="icon-button !h-8 !w-8" title="Edit" onClick={() => { setEditing(e); setOpen(true); }} data-testid={`expense-edit-${e.id}`}><Pencil size={14} /></button>
                    <button className="icon-button !h-8 !w-8 !text-[#A8221A]" title="Hapus" onClick={() => setDelTarget(e)} data-testid={`expense-delete-${e.id}`}><Trash2 size={14} /></button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}
      <ExpenseFormDialog open={open} onOpenChange={setOpen} initial={editing} onSaved={() => { load(); onChanged && onChanged(); }} />
      <ConfirmDialog open={Boolean(delTarget)} onOpenChange={(v) => !v && setDelTarget(null)} title="Hapus pengeluaran?"
        description={delTarget ? `${CAT_LABEL[delTarget.category] || delTarget.category} ${formatCurrency(delTarget.amount)} akan dihapus permanen.` : ""}
        busy={busy} onConfirm={doDelete} testId="expense-delete-confirm" />
    </div>
  );
}

function Invoices({ onChanged }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [delTarget, setDelTarget] = useState(null);
  const [busy, setBusy] = useState(false);
  const [waBusy, setWaBusy] = useState("");

  const doDelete = async () => {
    if (!delTarget) return;
    setBusy(true);
    try {
      await apiClient.delete(`/invoices/${delTarget.id}`);
      toast.success(`Invoice ${delTarget.number} dihapus`);
      setDelTarget(null); load(); onChanged && onChanged();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menghapus invoice"); }
    finally { setBusy(false); }
  };

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get("/invoices")
      .then((r) => { setRows(Array.isArray(r.data) ? r.data : []); setError(null); })
      .catch(() => setError("Gagal memuat invoice"))
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  const setStatus = async (id, status) => {
    try { await apiClient.patch(`/invoices/${id}`, { status }); toast.success("Status invoice diperbarui"); load(); onChanged && onChanged(); }
    catch (e) { toast.error("Gagal memperbarui status"); }
  };

  const sendWa = async (id) => {
    setWaBusy(id);
    try {
      const r = await apiClient.post(`/invoices/${id}/send-wa`);
      toast.success(`Invoice ${r.data?.number || ""} terkirim via WhatsApp`);
      load(); onChanged && onChanged();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal mengirim invoice via WhatsApp"); }
    finally { setWaBusy(""); }
  };

  const addBtn = (
    <button className="primary-button" onClick={() => setOpen(true)} data-testid="invoice-add"><Plus size={14} /> Buat Invoice</button>
  );

  return (
    <div className="space-y-3" data-testid="invoices-panel">
      <div className="flex justify-end">{addBtn}</div>
      {loading ? <LoadingState testId="invoices-loading" />
        : error ? <ErrorState message={error} onRetry={load} />
        : rows.length === 0 ? <EmptyState title="Belum ada invoice" description="Terbitkan faktur dari booking." testId="invoices-empty" action={addBtn} />
        : (
          <section className="section-card">
            <div className="section-head"><div className="flex items-center gap-2"><FileText size={16} className="text-[#007AFF]" /><h2>Daftar Invoice</h2></div></div>
            <div className="divide-y divide-[#F2F2F5]" data-testid="invoices-list">
              {rows.map((inv) => {
                const st = INV_STATUS[inv.status] || { l: inv.status, tone: "neutral" };
                return (
                  <div key={inv.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3" data-testid={`invoice-${inv.id}`}>
                    <div className="min-w-0">
                      <p className="flex items-center gap-2 text-[13px] font-bold text-[#1C1C1E]">
                        <span className="font-mono">{inv.number}</span>
                        <span className={`status-pill ${KIND_TONE[inv.kind] || "tone-neutral"}`} data-testid={`invoice-kind-${inv.id}`}>{inv.kind_label || "Tagihan"}</span>
                        <span className={`status-pill tone-${st.tone}`}>{st.l}</span>
                      </p>
                      <p className="truncate text-[11.5px] text-[#6B6B73]">{inv.customer_name} · {inv.booking_code} · jatuh tempo {formatDate(inv.due_at)}{inv.kind === "dp" ? ` · DP ${inv.dp_percent}%` : ""}{inv.subtotal ? ` · total ${formatCurrency(inv.subtotal)}` : ""}</p>
                    </div>
                    <div className="flex flex-shrink-0 items-center gap-2">
                      <span className="text-[14px] font-bold tabular-nums text-[#1C1C1E]">{formatCurrency(inv.amount)}</span>
                      <Select value={inv.status} onValueChange={(v) => setStatus(inv.id, v)}>
                        <SelectTrigger className="h-8 w-[120px]" data-testid={`invoice-status-${inv.id}`}><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {Object.entries(INV_STATUS).map(([v, o]) => <SelectItem key={v} value={v}>{o.l}</SelectItem>)}
                        </SelectContent>
                      </Select>
                      <button className="icon-button !h-8 !w-8" title="Lihat PDF" onClick={() => openPdf(`/invoices/${inv.id}/pdf`)} data-testid={`invoice-view-${inv.id}`}><Eye size={14} /></button>
                      <button className="icon-button !h-8 !w-8 !text-[#127A36]" title="Kirim PDF via WhatsApp" disabled={waBusy === inv.id} onClick={() => sendWa(inv.id)} data-testid={`invoice-wa-${inv.id}`}>{waBusy === inv.id ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}</button>
                      <button className="icon-button !h-8 !w-8" title="Unduh PDF" onClick={() => downloadFile(`/invoices/${inv.id}/export?format=pdf`, `${inv.number}.pdf`)} data-testid={`invoice-pdf-${inv.id}`}><Download size={14} /></button>
                      <button className="icon-button !h-8 !w-8" title="Unduh Excel" onClick={() => downloadFile(`/invoices/${inv.id}/export?format=excel`, `${inv.number}.xlsx`)} data-testid={`invoice-xlsx-${inv.id}`}><FileSpreadsheet size={14} /></button>
                      <button className="icon-button !h-8 !w-8" title="Edit" onClick={() => setEditing(inv)} data-testid={`invoice-edit-${inv.id}`}><Pencil size={14} /></button>
                      {["draft", "void"].includes(inv.status) ? (
                        <button className="icon-button !h-8 !w-8 !text-[#A8221A]" title="Hapus" onClick={() => setDelTarget(inv)} data-testid={`invoice-delete-${inv.id}`}><Trash2 size={14} /></button>
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}
      <InvoiceFormDialog open={open} onOpenChange={setOpen} onSaved={() => { load(); onChanged && onChanged(); }} />
      <InvoiceEditDialog open={Boolean(editing)} onOpenChange={(v) => !v && setEditing(null)} invoice={editing} onSaved={() => { load(); onChanged && onChanged(); }} />
      <ConfirmDialog open={Boolean(delTarget)} onOpenChange={(v) => !v && setDelTarget(null)} title="Hapus invoice?"
        description={delTarget ? `Invoice ${delTarget.number} (${formatCurrency(delTarget.amount)}) akan dihapus permanen.` : ""}
        busy={busy} onConfirm={doDelete} testId="invoice-delete-confirm" />
    </div>
  );
}

function Receivables({ onChanged }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [payBooking, setPayBooking] = useState(null);
  const [remindingAll, setRemindingAll] = useState(false);
  const [remindingId, setRemindingId] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    apiClient.get("/finance/ar")
      .then((r) => { setData(r.data); setError(null); })
      .catch(() => setError("Gagal memuat piutang"))
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  const remindOne = async (bookingId) => {
    setRemindingId(bookingId);
    try {
      const r = await apiClient.post(`/finance/ar/${bookingId}/remind`);
      toast.success(r.data?.sent ? `Reminder WA terkirim ke ${r.data.customer_name || "pelanggan"}` : "Reminder diproses");
    } catch (e) {
      toast.error("Gagal mengirim reminder");
    } finally { setRemindingId(""); }
  };

  const remindAll = async () => {
    setRemindingAll(true);
    try {
      const r = await apiClient.post("/finance/ar/remind-all");
      const sent = r.data?.sent ?? 0;
      toast.success(sent > 0 ? `${sent} reminder WA terkirim` : "Tidak ada piutang jatuh tempo untuk diingatkan");
    } catch (e) {
      toast.error("Gagal mengirim reminder massal");
    } finally { setRemindingAll(false); }
  };

  if (loading) return <LoadingState testId="ar-loading" />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  const rows = data?.items || [];
  if (rows.length === 0) return <EmptyState title="Tidak ada piutang" description="Semua tagihan sudah lunas." testId="ar-empty" />;

  return (
    <div className="space-y-3" data-testid="ar-panel">
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-[12px] bg-[rgba(255,149,0,0.10)] px-4 py-3">
        <span className="text-[13px] font-semibold text-[#8C4A00]">Total Piutang ({data.count} booking)</span>
        <div className="flex items-center gap-3">
          <span className="text-[16px] font-bold tabular-nums text-[#8C4A00]">{formatCurrency(data.total_outstanding)}</span>
          <button className="primary-button" disabled={remindingAll} onClick={remindAll} data-testid="ar-remind-all">
            {remindingAll ? <Loader2 size={14} className="animate-spin" /> : <BellRing size={14} />} Ingatkan Semua (WA)
          </button>
        </div>
      </div>
      <section className="section-card">
        <div className="section-head"><div className="flex items-center gap-2"><Wallet size={16} className="text-[#FF9500]" /><h2>Daftar Piutang</h2></div></div>
        <div className="divide-y divide-[#F2F2F5]" data-testid="ar-list">
          {rows.map((r) => {
            const age = daysSince(r.start_datetime);
            return (
              <div key={r.booking_id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3" data-testid={`ar-${r.booking_id}`}>
                <div className="min-w-0">
                  <p className="flex items-center gap-2 text-[13px] font-bold text-[#1C1C1E]">
                    {r.code} · {r.customer_name}
                    {age != null && age > 0 ? <span className="status-pill tone-danger" data-testid={`ar-age-${r.booking_id}`}>{age} hari</span> : null}
                  </p>
                  <p className="text-[11.5px] text-[#6B6B73]">Total {formatCurrency(r.total_amount)} · terbayar {formatCurrency(r.paid_amount)} · mulai {formatDate(r.start_datetime)}</p>
                </div>
                <div className="flex flex-shrink-0 items-center gap-3">
                  <div className="text-right">
                    <p className="text-[10.5px] uppercase text-[#8E8E93]">Sisa</p>
                    <p className="text-[14px] font-bold tabular-nums text-[#A8221A]">{formatCurrency(r.outstanding)}</p>
                  </div>
                  <PaymentPill value={r.payment_status} />
                  <button className="secondary-button" disabled={remindingId === r.booking_id} onClick={() => remindOne(r.booking_id)} data-testid={`ar-remind-${r.booking_id}`}>
                    {remindingId === r.booking_id ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />} Ingatkan
                  </button>
                  <button className="secondary-button" onClick={() => setPayBooking({ id: r.booking_id, code: r.code, customer_name: r.customer_name, total_amount: r.total_amount, paid_amount: r.paid_amount })} data-testid={`ar-pay-${r.booking_id}`}><Wallet size={13} /> Bayar</button>
                </div>
              </div>
            );
          })}
        </div>
      </section>
      <PaymentDialog open={Boolean(payBooking)} onOpenChange={(v) => !v && setPayBooking(null)} booking={payBooking} onSaved={() => { load(); onChanged && onChanged(); }} />
    </div>
  );
}
