// DepartureDetailPanel.jsx — detail satu keberangkatan + tindakan ops + peringatan risiko.
import {
  ArrowLeft, MapPin, Phone, Bus, User, Clock, Route as RouteIcon, CalendarDays,
  CheckCircle2, StickyNote, ChevronRight, ShieldCheck, Wallet, Pencil, CalendarClock,
  AlertTriangle,
} from "lucide-react";
import { StatusPill, PaymentPill } from "@/components/shared/StatusPill";
import { LoadingState } from "@/components/shared/DataStates";
import SelectField from "@/components/shared/SelectField";
import { formatCurrency, formatDateTime, formatDate } from "@/utils/formatters";
import { RiskIcon } from "./RiskIndicators";
import { STATUS_TONE, TONE_DOT, ACTIVE, severityStyleOf, riskStyleOf, vtypeLabel } from "./calendarCore";

function Field({ icon: Icon, label, children, testId }) {
  return (
    <div className="flex items-start gap-2.5" data-testid={testId}>
      <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-[#F1F2F6] text-[#6B6B73]"><Icon size={14} /></span>
      <div className="min-w-0">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-[#9A9AA0]">{label}</p>
        <div className="mt-0.5 text-[13.5px] text-[#1C1C1E]">{children}</div>
      </div>
    </div>
  );
}

function RiskAlert({ risk, onOpenRelated }) {
  if (!risk) return null;
  const sv = severityStyleOf(risk.severity);
  return (
    <div className="rounded-xl border p-3" data-testid="dc-detail-risks"
      style={{ borderColor: sv.border, background: sv.bg }}>
      <p className="mb-1.5 inline-flex items-center gap-1.5 text-[12px] font-bold" style={{ color: sv.fg }}>
        <AlertTriangle size={14} /> Perlu perhatian · {sv.label}
      </p>
      <div className="space-y-1.5">
        {risk.risks.map((r) => {
          const st = riskStyleOf(r.type);
          return (
            <div key={r.type} className="flex items-start gap-2" data-testid={`dc-detail-risk-${r.type}`}>
              <span className="mt-[3px]"><RiskIcon type={r.type} size={12} color={st.fg} /></span>
              <p className="text-[12px] leading-snug text-[#3a3f4a]">
                <span className="font-bold" style={{ color: st.fg }}>{r.label}</span> — {r.message}
                {(r.related || []).map((rel) => (
                  <button key={rel.id} onClick={() => onOpenRelated(rel.id)}
                    data-testid={`dc-detail-related-${rel.code}`}
                    className="ml-1.5 font-mono text-[11.5px] font-bold text-[#007AFF] underline decoration-dotted">
                    buka {rel.code}
                  </button>
                ))}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function DepartureDetailPanel({
  detail, loading, maps, vehicleColors, canManage, risk, busy,
  assignDriverId, setAssignDriverId, onAssign, onBack, onOpenRelated,
  onApprove, onReject, onComplete, onEdit, onReschedule, onPay, onCancel,
}) {
  if (loading) return <div className="py-12"><LoadingState testId="dc-detail-loading" /></div>;
  if (!detail) return null;
  const b = detail;
  const veh = maps.vehicles[b.vehicle_id] || {};
  const cust = maps.customers[b.customer_id] || {};
  const sisa = Math.max((Number(b.total_amount) || 0) - (Number(b.paid_amount) || 0), 0);
  const payments = Array.isArray(b.payments) ? b.payments : [];
  const canAssign = canManage && !["cancelled", "completed"].includes(b.status);
  const canPay = !["cancelled", "pending"].includes(b.status) && !["lunas", "selesai"].includes(b.payment_status);

  return (
    <div className="space-y-4" data-testid="dc-detail">
      <button onClick={onBack} className="inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-[#007AFF] hover:underline" data-testid="dc-detail-back">
        <ArrowLeft size={14} /> Kembali ke daftar
      </button>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="font-mono text-[15px] font-bold text-[#1C1C1E]">{b.code}</p>
          <p className="text-[12px] text-[#8E8E93]">Dibuat {formatDate(b.created_at)}{b.source === "public" ? " · dari situs publik" : ""}</p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <StatusPill value={b.status} tone={STATUS_TONE[b.status] || "neutral"} testId="dc-detail-status" />
          <PaymentPill value={b.payment_status} testId="dc-detail-payment" />
        </div>
      </div>

      <RiskAlert risk={risk} onOpenRelated={onOpenRelated} />

      <div className="grid grid-cols-1 gap-3.5 rounded-xl border border-[#EFF0F2] bg-[#FBFBFD] p-3.5">
        <Field icon={User} label="Pelanggan" testId="dc-f-customer">
          <span className="font-semibold">{b.customer_name || "-"}</span>
          {cust.phone ? <a href={`tel:${cust.phone}`} className="mt-0.5 flex items-center gap-1 text-[12.5px] text-[#007AFF]"><Phone size={12} /> {cust.phone}</a> : null}
        </Field>
        <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
          <Field icon={Bus} label="Armada" testId="dc-f-vehicle">
            <span className="inline-flex items-center gap-1.5 font-semibold">
              <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: vehicleColors[b.vehicle_name] || TONE_DOT.neutral }} />
              {b.vehicle_name || <span className="text-[#B0B1B8]">Belum ditetapkan</span>}
            </span>
            <p className="text-[12px] text-[#8E8E93]">
              {veh.plate_number ? `${veh.plate_number} · ` : ""}
              {veh.capacity ? `${veh.capacity} kursi` : (b.requested_vehicle_type ? `diminta: ${vtypeLabel(b.requested_vehicle_type)}${b.pax ? ` · ${b.pax} pax` : ""}` : "kapasitas -")}
            </p>
          </Field>
          <Field icon={User} label="Sopir" testId="dc-f-driver">{b.driver_name || <span className="text-[#B0B1B8]">Belum ditugaskan</span>}</Field>
        </div>
        <Field icon={RouteIcon} label="Rute" testId="dc-f-route">
          <span className="inline-flex items-center gap-1.5"><MapPin size={12} className="text-[#8E8E93]" />{b.origin || "-"}<ChevronRight size={12} className="text-[#B0B1B8]" />{b.destination || "-"}</span>
        </Field>
        <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
          <Field icon={CalendarDays} label="Berangkat" testId="dc-f-start">{formatDateTime(b.start_datetime)}</Field>
          <Field icon={Clock} label="Kembali" testId="dc-f-end">{formatDateTime(b.end_datetime)}</Field>
        </div>
        {b.notes ? <Field icon={StickyNote} label="Catatan" testId="dc-f-notes"><span className="text-[13px] text-[#3a3f4a]">{b.notes}</span></Field> : null}
      </div>

      {canAssign ? (
        <div className="rounded-xl border border-[#EFF0F2] p-3.5" data-testid="dc-assign-driver">
          <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-[#9A9AA0]">Tugaskan / Ganti Sopir</p>
          <div className="flex items-center gap-2">
            <div className="flex-1">
              <SelectField
                value={assignDriverId} onChange={setAssignDriverId} testId="dc-assign-select"
                className="w-full" placeholder="Pilih sopir" ariaLabel="Pilih sopir"
                options={[{ value: "", label: "— Tanpa sopir —" },
                  ...(maps.drivers || []).map((d) => ({ value: d.id, label: `${d.name}${d.phone ? ` · ${d.phone}` : ""}` }))]} />
            </div>
            <button className="primary-button" disabled={busy || assignDriverId === (b.driver_id || "")} onClick={onAssign} data-testid="dc-assign-save">
              {busy ? "…" : "Tugaskan"}
            </button>
          </div>
        </div>
      ) : null}

      <div className="rounded-xl border border-[#EFF0F2] p-3.5">
        <div className="flex items-center justify-between text-[13px]"><span className="text-[#6B6B73]">Total</span><span className="font-bold tabular-nums text-[#1C1C1E]">{formatCurrency(b.total_amount)}</span></div>
        <div className="mt-1 flex items-center justify-between text-[13px]"><span className="text-[#6B6B73]">Dibayar</span><span className="tabular-nums text-[#126E2C]">{formatCurrency(b.paid_amount)}</span></div>
        <div className="mt-1 flex items-center justify-between border-t border-[#EFF0F2] pt-1 text-[13px]"><span className="font-semibold text-[#6B6B73]">Sisa</span><span className="font-bold tabular-nums text-[#A8221A]">{formatCurrency(sisa)}</span></div>
        {payments.length ? (
          <div className="mt-2 space-y-1 border-t border-[#EFF0F2] pt-2" data-testid="dc-payments">
            {payments.map((p, i) => (
              <div key={p.id || i} className="flex items-center justify-between text-[12px] text-[#6B6B73]">
                <span>{formatDate(p.paid_at)} · {p.method || "pembayaran"}</span>
                <span className="tabular-nums">{formatCurrency(p.amount)}</span>
              </div>
            ))}
          </div>
        ) : null}
      </div>

      {canManage ? (
        <div className="flex flex-wrap gap-2" data-testid="dc-detail-actions">
          {b.status === "pending" ? (
            <>
              <button className="secondary-button !text-[#126E2C]" disabled={busy} onClick={onApprove} data-testid="dc-approve"><ShieldCheck size={14} /> Setujui</button>
              <button className="secondary-button !text-[#A8221A]" disabled={busy} onClick={onReject} data-testid="dc-reject">Tolak</button>
            </>
          ) : (
            <>
              {canPay ? <button className="secondary-button" onClick={onPay} data-testid="dc-pay"><Wallet size={14} /> Bayar</button> : null}
              {ACTIVE.includes(b.status) ? (
                <>
                  <button className="secondary-button" onClick={onEdit} data-testid="dc-edit"><Pencil size={14} /> Edit</button>
                  <button className="secondary-button" onClick={onReschedule} data-testid="dc-reschedule"><CalendarClock size={14} /> Jadwal ulang</button>
                  <button className="secondary-button" disabled={busy} onClick={onComplete} data-testid="dc-complete"><CheckCircle2 size={14} /> Selesai</button>
                  <button className="secondary-button !text-[#A8221A]" disabled={busy} onClick={onCancel} data-testid="dc-cancel">Batal</button>
                </>
              ) : null}
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}
