import { Eye } from "lucide-react";

// PreviewBanner — CMS-05: penanda JELAS bahwa halaman ini dibuka lewat tautan pratinjau
// (konten masih draft/terjadwal). Tanpa penanda ini editor mudah keliru menyangka konten
// sudah tayang untuk pengunjung.
export default function PreviewBanner({ status = "draft", testId = "preview-banner" }) {
  const label = status === "scheduled" ? "terjadwal terbit" : "draft";
  return (
    <div className="fixed inset-x-0 top-0 z-[70] bg-[#B45309] px-4 py-2 text-center text-[12.5px] font-semibold text-white shadow-lg"
      data-testid={testId}>
      <span className="inline-flex items-center gap-2">
        <Eye size={14} /> Mode pratinjau — konten ini {label} dan BELUM terlihat oleh pengunjung.
      </span>
    </div>
  );
}
