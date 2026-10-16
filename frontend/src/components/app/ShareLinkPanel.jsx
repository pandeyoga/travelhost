import { useCallback, useEffect, useState } from "react";
import { Share2, Link2, Copy, Ban, Trash2, Plus, Clock, Loader2 } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/services/apiClient";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { formatDateTime, formatQty } from "@/utils/formatters";

const EXPIRY_OPTS = [
  { v: "24", l: "24 jam" }, { v: "72", l: "3 hari" }, { v: "168", l: "7 hari" }, { v: "720", l: "30 hari" },
];
const TRIP_LABEL = { standby: "Standby", to_pickup: "Menuju Penjemputan", on_trip: "Dalam Perjalanan", completed: "Selesai" };

function shareUrl(token) {
  return `${window.location.origin}/track/${token}`;
}

// Panel kelola share-link tracking korporat (token + expiry + revoke).
export default function ShareLinkPanel({ trips = [] }) {
  const [shares, setShares] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tripId, setTripId] = useState("");
  const [label, setLabel] = useState("");
  const [hours, setHours] = useState("72");
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await apiClient.get("/shares");
      setShares(Array.isArray(r.data) ? r.data : []);
    } catch (e) {
      setShares([]);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (!tripId && trips.length) setTripId(trips[0].id); }, [trips, tripId]);

  const create = async () => {
    if (!tripId) { toast.error("Pilih trip untuk dibagikan"); return; }
    setCreating(true);
    try {
      await apiClient.post("/shares", { trip_id: tripId, label: label.trim(), hours: Number(hours) });
      toast.success("Tautan pelacakan dibuat");
      setLabel("");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal membuat tautan");
    } finally { setCreating(false); }
  };

  const copy = async (token) => {
    try {
      await navigator.clipboard.writeText(shareUrl(token));
      toast.success("Tautan disalin ke clipboard");
    } catch (e) {
      toast.message(shareUrl(token));
    }
  };

  const revoke = async (s) => {
    try { await apiClient.post(`/shares/${s.id}/revoke`, {}); toast.success("Tautan dinonaktifkan"); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Gagal menonaktifkan"); }
  };
  const remove = async (s) => {
    try { await apiClient.delete(`/shares/${s.id}`); toast.success("Tautan dihapus"); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Gagal menghapus"); }
  };

  const statusPill = (s) => {
    if (s.revoked) return <span className="status-pill tone-neutral">Dinonaktifkan</span>;
    if (s.expired) return <span className="status-pill tone-danger">Kedaluwarsa</span>;
    return <span className="status-pill tone-success">Aktif</span>;
  };

  return (
    <div className="section-card" data-testid="share-link-panel">
      <div className="section-head">
        <div className="flex min-w-0 items-center gap-2">
          <Share2 size={16} className="text-[#007AFF]" />
          <h2 className="truncate">Tautan Pelacakan Korporat</h2>
        </div>
      </div>
      <div className="section-body space-y-4">
        <p className="text-[12px] text-[#6B6B73]">
          Bagikan posisi armada ke customer korporat tanpa login. Tautan berbatas waktu &amp; bisa dinonaktifkan kapan saja.
        </p>

        {/* Form buat tautan */}
        <div className="grid grid-cols-1 gap-2 rounded-[12px] border border-[#EFF0F2] bg-[#FAFAFB] p-3 sm:grid-cols-12">
          <div className="sm:col-span-5">
            <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">Trip</label>
            <Select value={tripId} onValueChange={setTripId}>
              <SelectTrigger data-testid="share-trip-select"><SelectValue placeholder="Pilih trip" /></SelectTrigger>
              <SelectContent>
                {trips.map((t) => (
                  <SelectItem key={t.id} value={t.id}>{(t.dest_name || "Trip")} — {TRIP_LABEL[t.status] || t.status}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="sm:col-span-4">
            <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">Label (opsional)</label>
            <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="PT Maju Jaya" data-testid="share-label" />
          </div>
          <div className="sm:col-span-3">
            <label className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">Berlaku</label>
            <Select value={hours} onValueChange={setHours}>
              <SelectTrigger data-testid="share-hours"><SelectValue /></SelectTrigger>
              <SelectContent>{EXPIRY_OPTS.map((o) => <SelectItem key={o.v} value={o.v}>{o.l}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="sm:col-span-12">
            <button className="primary-button w-full sm:w-auto" disabled={creating || !tripId} onClick={create} data-testid="share-create-button">
              {creating ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />} Buat Tautan
            </button>
          </div>
        </div>

        {/* Daftar tautan */}
        {loading ? (
          <p className="py-6 text-center text-[12px] text-[#8E8E93]">Memuat tautan…</p>
        ) : shares.length === 0 ? (
          <p className="py-6 text-center text-[12px] text-[#8E8E93]" data-testid="share-empty">Belum ada tautan pelacakan dibuat.</p>
        ) : (
          <ul className="divide-y divide-[#F2F2F5] rounded-[12px] border border-[#EFF0F2]" data-testid="share-list">
            {shares.map((s) => (
              <li key={s.id} className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between" data-testid={`share-item-${s.id}`}>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <Link2 size={14} className="text-[#007AFF]" />
                    <span className="truncate text-[13px] font-semibold text-[#1C1C1E]">{s.label || s.vehicle_name || "Tracking"}</span>
                    {statusPill(s)}
                  </div>
                  <div className="mt-1 flex items-center gap-1 text-[11px] text-[#8E8E93]">
                    <Clock size={11} /> Berlaku s/d {formatDateTime(s.expires_at)} · {formatQty(s.access_count || 0)}× dilihat
                  </div>
                </div>
                <div className="flex flex-shrink-0 gap-1.5">
                  <button className="secondary-button !h-8" onClick={() => copy(s.token)} data-testid={`share-copy-${s.id}`}><Copy size={13} /> Salin</button>
                  {!s.revoked ? (
                    <button className="icon-button !h-8 !w-8 !text-[#C25400]" title="Nonaktifkan" onClick={() => revoke(s)} data-testid={`share-revoke-${s.id}`}><Ban size={14} /></button>
                  ) : null}
                  <button className="icon-button !h-8 !w-8 !text-[#A8221A]" title="Hapus" onClick={() => remove(s)} data-testid={`share-delete-${s.id}`}><Trash2 size={14} /></button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
