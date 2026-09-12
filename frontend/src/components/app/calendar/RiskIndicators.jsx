// RiskIndicators.jsx — atom visual untuk lapisan risiko kalender.
// Sengaja TANPA iterasi list (hanya 1 risiko per komponen) supaya tetap ringan
// dan bisa dipakai di sel kalender yang padat.
import {
  AlertTriangle, Users, Wrench, Hourglass, Clock, UserX, Inbox, Wallet,
} from "lucide-react";
import { riskStyleOf, severityStyleOf, riskLabel } from "./calendarCore";

const ICONS = {
  vehicle_conflict: AlertTriangle,
  driver_conflict: Users,
  maintenance_conflict: Wrench,
  hold_expired: Hourglass,
  hold_expiring: Clock,
  no_driver: UserX,
  pending_request: Inbox,
  unpaid_soon: Wallet,
};

export function RiskIcon({ type, size = 12, color, className = "" }) {
  const Ico = ICONS[type] || AlertTriangle;
  return <Ico size={size} className={`shrink-0 ${className}`} style={color ? { color } : undefined} aria-hidden="true" />;
}

export function SeverityDot({ severity, size = 8 }) {
  const st = severityStyleOf(severity);
  return (
    <span className="inline-block shrink-0 rounded-full" aria-hidden="true"
      style={{ width: size, height: size, background: st.ring }} />
  );
}

/** Badge kecil (label risiko) — dipakai di day-list & panel detail. */
export function RiskBadge({ type, testId, withLabel = true }) {
  const st = riskStyleOf(type);
  return (
    <span data-testid={testId} title={riskLabel(type)}
      className="inline-flex items-center gap-1 rounded-md px-1.5 py-[1px] text-[10px] font-bold leading-[15px]"
      style={{ background: st.bg, color: st.fg, border: `1px solid ${st.border}` }}>
      <RiskIcon type={type} size={9} />
      {withLabel ? riskLabel(type) : null}
    </span>
  );
}

/** Chip filter (klik untuk menyaring kalender per kelas risiko). */
export function RiskChip({ type, count, active, onClick, testId }) {
  const st = riskStyleOf(type);
  return (
    <button type="button" onClick={onClick} data-testid={testId} data-active={active ? "1" : "0"}
      aria-pressed={active}
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11.5px] font-bold transition ${active ? "ring-2 ring-offset-1" : "hover:brightness-[0.97]"}`}
      style={{
        background: st.bg, color: st.fg, border: `1px solid ${st.border}`,
        boxShadow: active ? `0 0 0 2px ${st.fg}22` : undefined,
        ...(active ? { outline: `1.5px solid ${st.fg}` } : null),
      }}>
      <RiskIcon type={type} size={11} />
      {riskLabel(type)}
      <span className="tabular-nums rounded-full bg-white/70 px-1.5 text-[10.5px] font-extrabold">{count}</span>
    </button>
  );
}
