import { useEffect, useState } from "react";
import { Loader2, AlarmClock, MapPin, MessageCircle } from "lucide-react";
import apiClient from "@/services/apiClient";
import { formatDate } from "@/utils/formatters";

const BUCKET = {
  overdue: { label: "Lewat tanggal", tone: "danger" }, h1: { label: "H-1", tone: "danger" },
  h3: { label: "H-3", tone: "warning" }, h7: { label: "H-7", tone: "info" },
};
const waOf = (p) => (p ? `https://wa.me/${String(p).replace(/[^0-9]/g, "").replace(/^0/, "62")}` : null);

export default function CrmReminders({ onOpen }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const load = () => {
    setLoading(true);
    apiClient.get("/leads/reminders").then((r) => { setRows(r.data || []); setError(null); }).catch(() => setError("Gagal memuat pengingat")).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  if (loading) return <div data-testid="crm-reminders"><div className="flex items-center justify-center py-16 text-[13px] text-[#6B6B73]" data-testid="reminders-loading"><Loader2 className="mr-2 animate-spin" /> Memuat pengingat…</div></div>;
  if (error) return <div data-testid="crm-reminders"><div className="py-16 text-center" data-testid="reminders-error"><p className="text-[#6B6B73]">{error}</p><button className="secondary-button mt-3" onClick={load}>Coba lagi</button></div></div>;
  if (rows.length === 0) return <div data-testid="crm-reminders"><div className="rounded-[14px] border border-dashed border-[#D9DADF] bg-white py-16 text-center text-[13px] text-[#6B6B73]" data-testid="reminders-empty">Tidak ada pengingat follow-up (H-7/H-3/H-1) untuk lead aktif.</div></div>;

  return (
    <div data-testid="crm-reminders">
      <div className="space-y-2" data-testid="reminders-list">
      {rows.map((r) => {
        const b = BUCKET[r.bucket] || { label: r.bucket, tone: "neutral" };
        const wa = waOf(r.phone);
        return (
          <div key={r.id} className="flex items-center justify-between gap-3 rounded-[12px] border border-[#EFF0F2] bg-white px-4 py-3" data-testid={`reminder-${r.id}`}>
            <button onClick={() => onOpen && onOpen(r.id)} className="flex min-w-0 items-center gap-3 text-left">
              <span className={`status-pill tone-${b.tone}`}><AlarmClock size={12} /> {b.label}</span>
              <div className="min-w-0">
                <p className="truncate text-[13px] font-bold text-[#1C1C1E]">{r.customer_name}</p>
                <p className="flex items-center gap-1 text-[11.5px] text-[#6B6B73]"><MapPin size={11} />{r.destination || "-"} · {formatDate(r.trip_date)}</p>
              </div>
            </button>
            {wa ? <a href={wa} target="_blank" rel="noreferrer" className="inline-flex flex-shrink-0 items-center gap-1.5 rounded-md bg-[#25D366] px-2.5 py-1.5 text-[11.5px] font-semibold text-white" data-testid={`reminder-wa-${r.id}`}><MessageCircle size={12} /> Ingatkan</a> : null}
          </div>
        );
      })}
      </div>
    </div>
  );
}
