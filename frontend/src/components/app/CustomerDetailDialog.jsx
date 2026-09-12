import { useEffect, useState } from "react";
import {
  Loader2, Phone, Mail, MapPin, CalendarRange, FileText, MessageSquare, UserPlus, Activity,
} from "lucide-react";
import apiClient from "@/services/apiClient";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { StatusPill, PaymentPill } from "@/components/shared/StatusPill";
import { formatCurrency, formatDateTime, formatQty } from "@/utils/formatters";

const STATUS_TONE = { confirmed: "info", ongoing: "warning", completed: "success", cancelled: "danger", draft: "neutral" };
const QUO_TONE = { draft: "neutral", sent: "info", accepted: "success", rejected: "danger", expired: "warning", converted: "purple" };
const TL_ICON = { booking: CalendarRange, quotation: FileText, lead: UserPlus, conversation: MessageSquare };

const TABS = [
  ["timeline", "Aktivitas", Activity],
  ["bookings", "Booking", CalendarRange],
  ["quotations", "Penawaran", FileText],
  ["leads", "Lead", UserPlus],
  ["conversations", "Percakapan", MessageSquare],
];

function Stat({ label, value }) {
  return (
    <div className="rounded-[12px] border border-[#EFF0F2] bg-white p-3">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-[#6B6B73]">{label}</p>
      <p className="mt-1 text-[18px] font-bold tabular-nums text-[#1C1C1E]" style={{ fontFamily: "Outfit, sans-serif" }}>{value}</p>
    </div>
  );
}

function Empty({ text, testId }) {
  return (
    <div className="rounded-[12px] border border-dashed border-[#D9DADF] bg-white px-4 py-8 text-center text-[13px] text-[#6B6B73]" data-testid={testId}>
      {text}
    </div>
  );
}

export default function CustomerDetailDialog({ open, onOpenChange, customerId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState("timeline");

  useEffect(() => {
    if (!open || !customerId) return;
    let active = true;
    setLoading(true); setData(null); setTab("timeline");
    apiClient.get(`/customers/${customerId}`)
      .then((r) => { if (active) setData(r.data); })
      .catch(() => { if (active) setData(null); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [open, customerId]);

  const stats = data?.stats || {};
  const bookings = Array.isArray(data?.bookings) ? data.bookings : [];
  const quotations = Array.isArray(data?.quotations) ? data.quotations : [];
  const leads = Array.isArray(data?.leads) ? data.leads : [];
  const conversations = Array.isArray(data?.conversations) ? data.conversations : [];
  const timeline = Array.isArray(data?.timeline) ? data.timeline : [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl" data-testid="customer-detail-dialog">
        <DialogHeader>
          <DialogTitle>{data?.name || "Contact 360"}</DialogTitle>
          <DialogDescription>Profil terpadu: booking, lead, penawaran & percakapan.</DialogDescription>
        </DialogHeader>
        {loading ? (
          <div className="flex items-center justify-center py-12 text-[13px] text-[#6B6B73]" data-testid="customer-detail-loading">
            <Loader2 size={16} className="mr-2 animate-spin" /> Memuat profil…
          </div>
        ) : !data ? (
          <div className="py-12 text-center text-[13px] text-[#6B6B73]">Gagal memuat profil customer.</div>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-3 text-[13px] text-[#3C3C43]">
              <span className="inline-flex items-center gap-1.5"><StatusPill value={data.type} tone={data.type === "corporate" ? "info" : "neutral"} /></span>
              {data.phone_normalized || data.phone ? <span className="inline-flex items-center gap-1.5" data-testid="customer-detail-phone"><Phone size={13} className="text-[#8E8E93]" /> {data.phone_normalized || data.phone}</span> : null}
              {data.email ? <span className="inline-flex items-center gap-1.5"><Mail size={13} className="text-[#8E8E93]" /> {data.email}</span> : null}
              {data.city ? <span className="inline-flex items-center gap-1.5"><MapPin size={13} className="text-[#8E8E93]" /> {data.city}</span> : null}
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat label="Booking" value={formatQty(stats.bookings_count)} />
              <Stat label="Total Dibayar" value={formatCurrency(stats.total_spent)} />
              <Stat label="Lead" value={formatQty(stats.leads_count)} />
              <Stat label="Penawaran" value={formatQty(stats.quotations_count)} />
            </div>

            <div className="tab-bar">
              {TABS.map(([k, l, Icon]) => (
                <button key={k} className={`tab-button ${tab === k ? "active" : ""}`} onClick={() => setTab(k)} data-testid={`cd360-tab-${k}`}>
                  <Icon size={14} /> {l}
                </button>
              ))}
            </div>

            {tab === "timeline" ? (
              timeline.length === 0 ? <Empty text="Belum ada aktivitas." testId="cd360-timeline-empty" /> : (
                <div className="space-y-2" data-testid="cd360-timeline">
                  {timeline.map((t, i) => {
                    const Icon = TL_ICON[t.type] || Activity;
                    return (
                      <div key={i} className="flex items-start gap-3 rounded-[12px] border border-[#EFF0F2] bg-white px-3 py-2.5" data-testid={`cd360-tl-${t.type}`}>
                        <span className="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-[#007AFF12] text-[#007AFF]"><Icon size={14} /></span>
                        <div className="min-w-0 flex-1">
                          <p className="flex items-center justify-between gap-2 text-[13px] font-semibold text-[#1C1C1E]">
                            <span className="truncate">{t.title}</span>
                            {typeof t.amount === "number" ? <span className="flex-shrink-0 tabular-nums">{formatCurrency(t.amount)}</span> : null}
                          </p>
                          <p className="flex items-center gap-2 text-[11.5px] text-[#6B6B73]">
                            <span className="truncate">{t.subtitle || "-"}</span>
                            {t.status ? <StatusPill value={t.status} tone={STATUS_TONE[t.status] || QUO_TONE[t.status] || "neutral"} /> : null}
                          </p>
                          <p className="text-[11px] text-[#A0A0A7]">{formatDateTime(t.date)}</p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )
            ) : null}

            {tab === "bookings" ? (
              bookings.length === 0 ? <Empty text="Belum ada booking." testId="cd360-bookings-empty" /> : (
                <div className="overflow-hidden rounded-[12px] border border-[#EFF0F2]" data-testid="cd360-bookings">
                  {bookings.map((b) => (
                    <div key={b.id} className="flex items-center justify-between gap-3 border-b border-[#F2F2F5] px-3 py-2.5 last:border-0">
                      <div className="min-w-0">
                        <p className="truncate text-[13px] font-semibold text-[#1C1C1E]">{b.code} · {b.vehicle_name || "-"}</p>
                        <p className="text-[11.5px] text-[#6B6B73]">{formatDateTime(b.start_datetime)}</p>
                      </div>
                      <div className="flex flex-shrink-0 items-center gap-2">
                        <span className="text-[13px] font-bold tabular-nums text-[#1C1C1E]">{formatCurrency(b.total_amount)}</span>
                        <PaymentPill value={b.payment_status} />
                        <StatusPill value={b.status} tone={STATUS_TONE[b.status] || "neutral"} />
                      </div>
                    </div>
                  ))}
                </div>
              )
            ) : null}

            {tab === "quotations" ? (
              quotations.length === 0 ? <Empty text="Belum ada penawaran." testId="cd360-quotations-empty" /> : (
                <div className="overflow-hidden rounded-[12px] border border-[#EFF0F2]" data-testid="cd360-quotations">
                  {quotations.map((q) => (
                    <div key={q.id} className="flex items-center justify-between gap-3 border-b border-[#F2F2F5] px-3 py-2.5 last:border-0">
                      <div className="min-w-0">
                        <p className="truncate text-[13px] font-semibold text-[#1C1C1E]">{q.number}</p>
                        <p className="text-[11.5px] text-[#6B6B73]">{q.destination || "-"} · {formatDateTime(q.created_at)}</p>
                      </div>
                      <div className="flex flex-shrink-0 items-center gap-2">
                        <span className="text-[13px] font-bold tabular-nums text-[#1C1C1E]">{formatCurrency(q.total)}</span>
                        <StatusPill value={q.status} tone={QUO_TONE[q.status] || "neutral"} />
                      </div>
                    </div>
                  ))}
                </div>
              )
            ) : null}

            {tab === "leads" ? (
              leads.length === 0 ? <Empty text="Belum ada lead." testId="cd360-leads-empty" /> : (
                <div className="overflow-hidden rounded-[12px] border border-[#EFF0F2]" data-testid="cd360-leads">
                  {leads.map((l) => (
                    <div key={l.id} className="flex items-center justify-between gap-3 border-b border-[#F2F2F5] px-3 py-2.5 last:border-0">
                      <div className="min-w-0">
                        <p className="truncate text-[13px] font-semibold text-[#1C1C1E]">{l.destination || "Lead"} · {l.source || "manual"}</p>
                        <p className="truncate text-[11.5px] text-[#6B6B73]">{l.message || "-"}</p>
                      </div>
                      <StatusPill value={l.stage} tone={l.stage === "won" ? "success" : l.stage === "lost" ? "danger" : "info"} />
                    </div>
                  ))}
                </div>
              )
            ) : null}

            {tab === "conversations" ? (
              conversations.length === 0 ? <Empty text="Belum ada percakapan." testId="cd360-conversations-empty" /> : (
                <div className="overflow-hidden rounded-[12px] border border-[#EFF0F2]" data-testid="cd360-conversations">
                  {conversations.map((c) => (
                    <div key={c.id} className="flex items-center justify-between gap-3 border-b border-[#F2F2F5] px-3 py-2.5 last:border-0">
                      <div className="min-w-0">
                        <p className="truncate text-[13px] font-semibold text-[#1C1C1E]">{c.subject || c.contact_name || "Percakapan"}</p>
                        <p className="text-[11.5px] text-[#6B6B73]">{c.channel || "internal"} · {formatDateTime(c.last_message_at || c.created_at)}</p>
                      </div>
                      <StatusPill value={c.status} tone={c.status === "open" ? "info" : c.status === "closed" ? "neutral" : "warning"} />
                    </div>
                  ))}
                </div>
              )
            ) : null}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
