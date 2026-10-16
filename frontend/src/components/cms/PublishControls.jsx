import { useState } from "react";
import { toast } from "sonner";
import { CalendarClock, Check, Copy, ExternalLink, Eye, Loader2 } from "lucide-react";
import apiClient from "@/services/apiClient";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

/**
 * PublishControls — CMS-05: siklus terbit satu konten (draft → terjadwal → tayang).
 *
 * Tiga hal yang dulu tidak mungkin dan kini bisa:
 *  1. **Menyimpan tanpa menayangkan.** Status `Draft` tidak pernah muncul di halaman publik
 *     maupun sitemap (predikat visibilitas dipakai bersama oleh daftar, detail, dan sitemap).
 *  2. **Menjadwalkan.** `Terjadwal` + tanggal/jam → penjadwal server menaikkan status sendiri
 *     saat waktunya lewat; konten yang jadwalnya sudah lewat langsung dianggap tayang
 *     (tidak menunggu siklus penjadwal berikutnya).
 *  3. **Pratinjau aman.** Tautan pratinjau bertoken (24 jam) membuka SATU dokumen ini saja —
 *     tanpa itu editor harus menayangkan dulu untuk melihat hasil akhir, artinya pengunjung
 *     dan mesin pencari melihat konten setengah jadi.
 */
const STATUSES = [
  ["draft", "Draft — belum terlihat publik"],
  ["scheduled", "Terjadwal — terbit otomatis"],
  ["published", "Tayang sekarang"],
];

/** ISO UTC → nilai untuk <input type="datetime-local"> (waktu lokal peramban). */
function isoToLocalInput(iso) {
  const raw = String(iso || "").trim();
  if (!raw) return "";
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Nilai datetime-local (waktu lokal) → ISO UTC, supaya server membandingkan apel dengan apel. */
export function localInputToIso(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return "";
  return d.toISOString().replace(/\.\d{3}Z$/, "+00:00");
}

export default function PublishControls({ resource, item, status, publishAt, onChange }) {
  const [minting, setMinting] = useState(false);
  const [preview, setPreview] = useState(null);
  const [copied, setCopied] = useState(false);
  const localValue = isoToLocalInput(publishAt);

  const mint = async () => {
    if (!item?.id) return;
    setMinting(true);
    try {
      const { data } = await apiClient.post(`/content/${resource}/${item.id}/preview-token`);
      setPreview(data);
      toast.success("Tautan pratinjau dibuat — berlaku 24 jam");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal membuat tautan pratinjau");
    } finally { setMinting(false); }
  };

  const previewHref = preview?.url && /^https?:/i.test(preview.url)
    ? preview.url
    : preview?.url ? `${window.location.origin}${preview.url.startsWith("/") ? "" : "/"}${preview.url}` : "";

  const copy = async () => {
    try { await navigator.clipboard.writeText(previewHref); setCopied(true); setTimeout(() => setCopied(false), 2000); toast.success("Tautan disalin"); }
    catch { toast.message(previewHref); }
  };

  return (
    <div className="space-y-3 rounded-[12px] border border-[#E5E5EA] bg-[#F7F8FA] p-3.5" data-testid="cf-publish-panel">
      <div className="space-y-1">
        <Label className="text-[12px]">Status terbit</Label>
        <Select value={status || "draft"} onValueChange={(v) => onChange({ status: v })}>
          <SelectTrigger data-testid="cf-status"><SelectValue placeholder="Pilih status…" /></SelectTrigger>
          <SelectContent>
            {STATUSES.map(([v, l]) => (
              <SelectItem key={v} value={v} data-testid={`cf-status-opt-${v}`}>{l}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {status === "scheduled" || localValue ? (
        <div className="space-y-1">
          <Label className="text-[12px]">Tanggal &amp; jam terbit</Label>
          <input type="datetime-local" value={localValue}
            onChange={(e) => onChange({ publish_at: localInputToIso(e.target.value) })}
            className="h-9 w-full rounded-[10px] border border-[#E5E5EA] bg-white px-3 text-[13px] text-[#1C1C1E] outline-none focus:border-[#0058CC]"
            data-testid="cf-publish-at" />
          <p className="text-[10.5px] text-[#8A8A8F]">
            Waktu mengikuti zona peramban Anda; server menyimpannya dalam UTC. Status
            <span className="font-semibold"> Terjadwal</span> wajib punya tanggal &amp; jam.
          </p>
        </div>
      ) : null}

      <div className="border-t border-[#E5E5EA] pt-3">
        {item?.id ? (
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" className="secondary-button" onClick={mint} disabled={minting}
              data-testid="cf-preview-token">
              {minting ? <Loader2 size={14} className="animate-spin" /> : <Eye size={14} />} Buat tautan pratinjau
            </button>
            {previewHref ? (
              <>
                <a href={previewHref} target="_blank" rel="noreferrer" className="secondary-button"
                  data-testid="cf-preview-open"><ExternalLink size={14} /> Buka</a>
                <button type="button" className="secondary-button" onClick={copy} data-testid="cf-preview-copy">
                  {copied ? <Check size={14} /> : <Copy size={14} />} Salin
                </button>
              </>
            ) : null}
          </div>
        ) : (
          <p className="flex items-start gap-1.5 text-[11.5px] text-[#6B6B73]">
            <CalendarClock size={13} className="mt-0.5 shrink-0" />
            Simpan dulu untuk bisa membuat tautan pratinjau (token menunjuk dokumen yang sudah ada).
          </p>
        )}
        {previewHref ? (
          <p className="mt-2 break-all rounded-md bg-white px-2 py-1.5 font-mono text-[10.5px] text-[#6B6B73]"
            data-testid="cf-preview-url">{previewHref}</p>
        ) : null}
      </div>
    </div>
  );
}
