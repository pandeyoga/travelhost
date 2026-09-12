import { MapPin, Navigation2, Play, Flag, CheckCircle2, Camera, Phone, CalendarClock, Bus, LogIn } from "lucide-react";
import { formatDateTime } from "@/utils/formatters";

const STATUS = {
  standby: { label: "Standby", tone: "neutral" },
  assigned: { label: "Ditugaskan", tone: "info" },
  to_pickup: { label: "Berangkat Jemput", tone: "warning" },
  on_trip: { label: "Dalam Perjalanan", tone: "info" },
  completed: { label: "Selesai", tone: "success" },
  cancelled: { label: "Dibatalkan", tone: "danger" },
};

// Stepper RC-D: standby → berangkat jemput → dalam perjalanan → tiba → check-out odometer.
const STEPS = ["Standby", "Jemput", "Jalan", "Tiba", "Selesai"];
function stepIndex(task) {
  if (task.trip_status === "completed") return 4;
  if (task.trip_status === "on_trip") return task.arrived ? 3 : 2;
  if (task.trip_status === "to_pickup") return 1;
  return 0;
}

function Stepper({ task }) {
  const idx = stepIndex(task);
  return (
    <div className="mt-3 flex items-center gap-1" data-testid={`dw-stepper-${task.trip_id}`}>
      {STEPS.map((s, i) => (
        <div key={s} className="flex flex-1 flex-col items-center gap-1">
          <div className={`h-1.5 w-full rounded-full ${i <= idx ? "bg-[#007AFF]" : "bg-[#E9E9EE]"}`} />
          <span className={`text-[10px] font-semibold ${i <= idx ? "text-[#007AFF]" : "text-[#B0B1B8]"}`}>{s}</span>
        </div>
      ))}
    </div>
  );
}

export default function DriverTaskCard({ task, busy, onAck, onDepart, onPickup, onArrived, onCheckout, onPod, onNav }) {
  const st = task.trip_status === "on_trip" && task.arrived
    ? { label: "Tiba di Tujuan", tone: "success" }
    : STATUS[task.trip_status] || { label: task.trip_status || "-", tone: "neutral" };
  const tid = task.trip_id;
  const done = task.trip_status === "completed";
  const hasCoords = task.dest_lat != null && task.dest_lng != null;
  const started = ["to_pickup", "on_trip"].includes(task.trip_status);

  return (
    <div className="rounded-[16px] border border-[#EFF0F2] bg-white p-4 shadow-sm" data-testid={`dw-task-${tid}`}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[14px] font-bold text-[#1C1C1E]" style={{ fontFamily: "Outfit, sans-serif" }}>{task.code || "Trip"}</span>
            <span className={`status-pill tone-${st.tone}`} data-testid={`dw-status-${tid}`}>{st.label}</span>
          </div>
          <div className="mt-0.5 text-[13px] font-semibold text-[#1C1C1E]">{task.customer_name || "-"}</div>
        </div>
        <div className="flex flex-wrap justify-end gap-1">
          {task.acknowledged ? <span className="status-pill tone-success" data-testid={`dw-badge-ack-${tid}`}>Dikonfirmasi</span> : null}
          {task.arrived ? <span className="status-pill tone-info">Tiba</span> : null}
          {task.has_pod ? <span className="status-pill tone-success" data-testid={`dw-badge-pod-${tid}`}>POD ✓</span> : null}
        </div>
      </div>

      <div className="mt-3 space-y-1.5 text-[12.5px] text-[#3A3A3C]">
        <div className="flex items-center gap-2"><MapPin size={14} className="text-[#007AFF]" /><span>{task.origin || "-"} → <b>{task.destination || "-"}</b></span></div>
        <div className="flex items-center gap-2"><CalendarClock size={14} className="text-[#8E8E93]" /><span className="tabular-nums">{formatDateTime(task.start_datetime)}</span></div>
        {task.vehicle_name ? <div className="flex items-center gap-2"><Bus size={14} className="text-[#8E8E93]" /><span>{task.vehicle_name}{task.vehicle_plate ? ` · ${task.vehicle_plate}` : ""}</span></div> : null}
        {task.customer_phone ? <div className="flex items-center gap-2"><Phone size={14} className="text-[#8E8E93]" /><span className="tabular-nums">{task.customer_phone}</span></div> : null}
      </div>

      {!done && task.trip_status !== "cancelled" ? <Stepper task={task} /> : null}

      <div className="mt-3 flex flex-wrap gap-2">
        {!task.acknowledged && !done ? (
          <button className="secondary-button !h-9" disabled={busy} onClick={() => onAck(task)} data-testid={`dw-ack-${tid}`}>
            <CheckCircle2 size={14} /> Konfirmasi Tugas
          </button>
        ) : null}
        <button className="secondary-button !h-9" disabled={!hasCoords} onClick={() => onNav(task)} data-testid={`dw-nav-${tid}`}>
          <Navigation2 size={14} /> Navigasi
        </button>

        {["standby", "assigned"].includes(task.trip_status) ? (
          <button className="primary-button !h-9" disabled={busy} onClick={() => onDepart(task)} data-testid={`dw-depart-${tid}`}>
            <Play size={14} /> Berangkat Jemput
          </button>
        ) : null}

        {task.trip_status === "to_pickup" ? (
          <button className="primary-button !h-9" disabled={busy} onClick={() => onPickup(task)} data-testid={`dw-pickup-${tid}`}>
            <LogIn size={14} /> Penumpang Naik — Mulai Perjalanan
          </button>
        ) : null}

        {task.trip_status === "on_trip" && !task.arrived ? (
          <button className="primary-button !h-9" disabled={busy} onClick={() => onArrived(task)} data-testid={`dw-arrived-${tid}`}>
            <Flag size={14} /> Tiba di Tujuan
          </button>
        ) : null}

        {task.trip_status === "on_trip" ? (
          <button className={`${task.arrived ? "primary-button" : "secondary-button"} !h-9`} disabled={busy}
            onClick={() => onCheckout(task)} data-testid={`dw-complete-${tid}`}>
            <CheckCircle2 size={14} /> Check-out Odometer
          </button>
        ) : null}

        {started || done ? (
          <button className="secondary-button !h-9" disabled={busy} onClick={() => onPod(task)} data-testid={`dw-pod-${tid}`}>
            <Camera size={14} /> {task.has_pod ? "Lihat / Ubah POD" : "Unggah POD"}
          </button>
        ) : null}
      </div>
    </div>
  );
}
