import { useState } from "react";
import { MapPin, Users } from "lucide-react";
import { formatCurrency, formatQty, initials } from "@/utils/formatters";

const STAGES = [
  { key: "new", label: "Baru", tone: "info" },
  { key: "contacted", label: "Dihubungi", tone: "info" },
  { key: "quoted", label: "Penawaran", tone: "warning" },
  { key: "negotiation", label: "Negosiasi", tone: "purple" },
  { key: "won", label: "Menang", tone: "success" },
  { key: "lost", label: "Hilang", tone: "danger" },
];
const SRC = { website: "Web", whatsapp: "WA", manual: "Manual", landing_page: "Iklan LP" };

export default function CrmKanban({ stages, loading, onOpen, onMove }) {
  const [dragId, setDragId] = useState(null);
  const [overKey, setOverKey] = useState(null);
  const byKey = {};
  (stages || []).forEach((s) => { byKey[s.key] = s; });

  const drop = (key) => { if (dragId) onMove(dragId, key); setDragId(null); setOverKey(null); };

  return (
    <div className="flex gap-3 overflow-x-auto pb-2" data-testid="crm-kanban">
      {STAGES.map((st) => {
        const col = byKey[st.key] || { count: 0, value: 0, leads: [] };
        const active = overKey === st.key;
        return (
          <div key={st.key}
            onDragOver={(e) => { e.preventDefault(); setOverKey(st.key); }}
            onDragLeave={() => setOverKey(null)}
            onDrop={() => drop(st.key)}
            className={`flex w-[268px] flex-shrink-0 flex-col rounded-[14px] border ${active ? "border-[#007AFF] bg-[#F0F6FF]" : "border-[#EFF0F2] bg-[#FAFAFB]"}`}
            data-testid={`kanban-col-${st.key}`}>
            <div className="flex items-center justify-between border-b border-[#EFF0F2] px-3 py-2.5">
              <span className={`status-pill tone-${st.tone}`}>{st.label}</span>
              <span className="text-[12px] font-bold tabular-nums text-[#6B6B73]">{col.count}</span>
            </div>
            <div className="px-3 pt-2 text-[11px] tabular-nums text-[#8E8E93]">{formatCurrency(col.value)}</div>
            <div className="flex min-h-[90px] flex-1 flex-col gap-2 p-2">
              {loading ? (
                Array.from({ length: 2 }).map((_, i) => <div key={i} className="h-[92px] animate-pulse rounded-[12px] bg-[#EEF1F6]" data-testid="kanban-skeleton" />)
              ) : col.leads.length === 0 ? (
                <p className="px-1 py-5 text-center text-[12px] text-[#A0A0A7]" data-testid={`kanban-empty-${st.key}`}>Belum ada lead</p>
              ) : (
                col.leads.map((l) => (
                  <button key={l.id} draggable
                    onDragStart={() => setDragId(l.id)} onDragEnd={() => setDragId(null)}
                    onClick={() => onOpen(l.id)}
                    className="w-full rounded-[12px] border border-[#EFF0F2] bg-white p-3 text-left shadow-[var(--shadow-1)] transition hover:border-[#CFE0FF] hover:shadow-md"
                    data-testid={`lead-card-${l.id}`}>
                    <div className="flex items-start justify-between gap-2">
                      <p className="truncate text-[13px] font-bold text-[#1C1C1E]">{l.customer_name}</p>
                      <span className="flex-shrink-0 rounded-md bg-[#F0F0F3] px-1.5 py-0.5 text-[10px] font-semibold text-[#6B6B73]">{SRC[l.source] || l.source}</span>
                    </div>
                    {l.destination ? <p className="mt-1 flex items-center gap-1 text-[11.5px] text-[#6B6B73]"><MapPin size={12} /> {l.destination}</p> : null}
                    <div className="mt-2 flex items-center justify-between">
                      <span className="inline-flex items-center gap-1 text-[11.5px] text-[#6B6B73]"><Users size={12} /> {formatQty(l.pax)}</span>
                      {l.value > 0 ? <span className="text-[12px] font-bold tabular-nums text-[#1C1C1E]">{formatCurrency(l.value)}</span> : null}
                    </div>
                    {l.assignee_name ? (
                      <div className="mt-2 flex items-center gap-1.5 border-t border-[#F2F2F5] pt-2">
                        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[#007AFF] text-[9px] font-bold text-white">{initials(l.assignee_name)}</span>
                        <span className="truncate text-[11px] text-[#6B6B73]">{l.assignee_name}</span>
                      </div>
                    ) : <p className="mt-2 border-t border-[#F2F2F5] pt-2 text-[11px] text-[#FF9500]">Belum ditugaskan</p>}
                  </button>
                ))
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
