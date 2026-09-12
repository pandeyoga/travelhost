import { useCallback, useEffect, useState } from "react";
import { Bell, CheckCheck, Wrench, UserPlus, CalendarClock, X, BellOff, IdCard, Receipt, Coins, Satellite } from "lucide-react";
import apiClient from "@/services/apiClient";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { formatDateTime } from "@/utils/formatters";

const TYPE_ICON = {
  document_reminder: Wrench, lead_followup: UserPlus, booking_reminder: CalendarClock,
  sim_reminder: IdCard, invoice_overdue: Receipt, payroll_reminder: Coins, gps_alarm: Satellite,
};
const TYPE_TINT = {
  document_reminder: "#FF9500", lead_followup: "#007AFF", booking_reminder: "#34C759",
  sim_reminder: "#FF3B30", invoice_overdue: "#FF3B30", payroll_reminder: "#5856D6", gps_alarm: "#FF3B30",
};

export default function NotificationBell() {
  const [count, setCount] = useState(0);
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const loadCount = useCallback(async () => {
    try {
      const r = await apiClient.get("/notifications/unread_count");
      setCount(r.data?.count || 0);
    } catch (e) { /* silent */ }
  }, []);

  const loadList = useCallback(async () => {
    setLoading(true);
    try {
      const r = await apiClient.get("/notifications?limit=25");
      setItems((Array.isArray(r.data) ? r.data : []).filter((n) => n.status !== "dismissed"));
    } catch (e) {
      setItems([]);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    loadCount();
    const t = setInterval(loadCount, 30000);
    return () => clearInterval(t);
  }, [loadCount]);

  useEffect(() => { if (open) loadList(); }, [open, loadList]);

  const markRead = async (id) => {
    try { await apiClient.post(`/notifications/${id}/read`); } catch (e) { /* */ }
    loadList(); loadCount();
  };
  const dismiss = async (id) => {
    try { await apiClient.post(`/notifications/${id}/dismiss`); } catch (e) { /* */ }
    loadList(); loadCount();
  };
  const readAll = async () => {
    try { await apiClient.post("/notifications/read_all"); } catch (e) { /* */ }
    loadList(); loadCount();
  };

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <button className="icon-button notif-button relative" data-testid="notification-button" aria-label="Notifikasi">
          <Bell size={15} />
          {count > 0 ? (
            <span
              data-testid="notification-badge"
              className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-[#FF3B30] px-1 text-[10px] font-bold leading-none text-white"
            >
              {count > 9 ? "9+" : count}
            </span>
          ) : null}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[340px] p-0">
        <div className="flex items-center justify-between border-b border-[#F0F0F2] px-3 py-2.5">
          <span className="text-[13px] font-semibold text-[#1C1C1E]">Notifikasi</span>
          <button className="flex items-center gap-1 text-[11px] font-semibold text-[#007AFF] hover:underline" onClick={readAll} data-testid="notif-read-all">
            <CheckCheck size={13} /> Tandai semua
          </button>
        </div>
        <div className="max-h-[60vh] overflow-y-auto" data-testid="notification-list">
          {loading ? (
            <div className="px-3 py-8 text-center text-[12px] text-[#8E8E93]">Memuat…</div>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center px-3 py-10 text-center text-[12px] text-[#8E8E93]" data-testid="notif-empty">
              <BellOff size={20} className="mb-2 text-[#C7C7CC]" /> Belum ada notifikasi.
            </div>
          ) : (
            items.map((n) => {
              const Icon = TYPE_ICON[n.type] || Bell;
              const unread = n.status === "pending";
              return (
                <div
                  key={n.id}
                  data-testid={`notif-item-${n.id}`}
                  className={`flex gap-2.5 border-b border-[#F5F5F7] px-3 py-2.5 ${unread ? "bg-[#F5F9FF]" : "bg-white"}`}
                >
                  <div className="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg" style={{ background: `${TYPE_TINT[n.type] || "#8E8E93"}1A` }}>
                    <Icon size={14} style={{ color: TYPE_TINT[n.type] || "#8E8E93" }} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-[12.5px] font-semibold leading-snug text-[#1C1C1E]">{n.title}</p>
                    <p className="mt-0.5 line-clamp-2 text-[11.5px] leading-snug text-[#6B6B73]">{n.body}</p>
                    <div className="mt-1 flex items-center gap-2">
                      <span className="text-[10.5px] text-[#A0A0A8]">{formatDateTime(n.created_at)}</span>
                      {unread ? (
                        <button className="text-[10.5px] font-semibold text-[#007AFF] hover:underline" onClick={() => markRead(n.id)} data-testid={`notif-read-${n.id}`}>Tandai dibaca</button>
                      ) : null}
                    </div>
                  </div>
                  <button className="flex-shrink-0 text-[#C7C7CC] hover:text-[#FF3B30]" onClick={() => dismiss(n.id)} title="Hapus" data-testid={`notif-dismiss-${n.id}`}>
                    <X size={14} />
                  </button>
                </div>
              );
            })
          )}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
