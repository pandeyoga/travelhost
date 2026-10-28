// DetailField.jsx — baris "ikon + label + isi" untuk detail keberangkatan.
// Dipakai panel detail Kalender (ERP) dan halaman jadwal publik (/schedule/:token).
export default function DetailField({ icon: Icon, label, children, testId }) {
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
