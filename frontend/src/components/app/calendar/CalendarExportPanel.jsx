// CalendarExportPanel.jsx — popover ekspor jadwal (PDF / Excel) dgn pilihan cakupan.
import { useEffect } from "react";
import { FileText, FileSpreadsheet, Download } from "lucide-react";

export default function CalendarExportPanel({
  open, onToggle, onClose, scope, setScope, scopeText, start, setStart, end, setEnd,
  group, setGroup, exporting, onExport,
}) {
  // Tutup dengan tombol Escape (temuan LOW iter-74): sebelumnya panel hanya bisa ditutup
  // dengan klik backdrop/tombol, padahal Escape adalah kebiasaan baku untuk popover/dialog.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <div className="relative">
      <button className="secondary-button" onClick={onToggle} data-testid="dc-export-open"
        aria-expanded={open} aria-haspopup="dialog">
        <Download size={14} /> Ekspor
      </button>
      {open ? (
        <>
          <div className="fixed inset-0 z-40" onClick={onClose} data-testid="dc-export-backdrop" />
          <div className="absolute right-0 z-50 mt-2 w-[300px] rounded-xl border border-[#E5E5EA] bg-white p-3.5 shadow-[0_12px_40px_rgba(0,0,0,0.14)]"
            role="dialog" aria-label="Ekspor jadwal keberangkatan" data-testid="dc-export-panel">
            <p className="mb-2 text-[13px] font-bold text-[#1C1C1E]">Ekspor Jadwal</p>
            <div className="space-y-1.5">
              <label className="flex items-center gap-2 text-[12.5px] text-[#1C1C1E]">
                <input type="radio" name="dc-scope" checked={scope === "active"} onChange={() => setScope("active")} data-testid="dc-scope-active" />
                Ikuti tampilan aktif
              </label>
              <p className="ml-6 -mt-1 text-[11.5px] font-medium text-[#007AFF]" data-testid="dc-scope-text">{scopeText}</p>
              <label className="flex items-center gap-2 text-[12.5px] text-[#1C1C1E]">
                <input type="radio" name="dc-scope" checked={scope === "custom"} onChange={() => setScope("custom")} data-testid="dc-scope-custom" />
                Rentang tanggal khusus
              </label>
              {scope === "custom" ? (
                <div className="ml-6 flex items-center gap-1.5">
                  <input type="date" value={start} onChange={(e) => setStart(e.target.value)} data-testid="dc-export-start"
                    className="h-8 w-[120px] rounded-md border border-[#E5E5EA] px-2 text-[12px] outline-none focus:border-[#007AFF]" />
                  <span className="text-[#8E8E93]">–</span>
                  <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} data-testid="dc-export-end"
                    className="h-8 w-[120px] rounded-md border border-[#E5E5EA] px-2 text-[12px] outline-none focus:border-[#007AFF]" />
                </div>
              ) : null}
            </div>
            <label className="mt-2.5 flex items-center gap-2 border-t border-[#F0F1F3] pt-2.5 text-[12.5px] text-[#1C1C1E]">
              <input type="checkbox" checked={group} onChange={(e) => setGroup(e.target.checked)} data-testid="dc-export-group" />
              Kelompokkan per armada
            </label>
            <div className="mt-3 flex gap-2">
              <button className="secondary-button flex-1 justify-center" disabled={exporting === "pdf"}
                onClick={() => onExport("pdf")} data-testid="dc-export-pdf">
                <FileText size={14} /> {exporting === "pdf" ? "…" : "PDF"}
              </button>
              <button className="secondary-button flex-1 justify-center" disabled={exporting === "excel"}
                onClick={() => onExport("excel")} data-testid="dc-export-excel">
                <FileSpreadsheet size={14} /> {exporting === "excel" ? "…" : "Excel"}
              </button>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
