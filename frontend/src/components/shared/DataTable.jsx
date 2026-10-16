import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

// Tabel data gaya "Kain Nusantara": dibungkus section-card, header muted, baris hover.
// State (loading/empty/error) ditangani di halaman pemanggil.
export default function DataTable({
  columns,
  rows,
  title,
  icon: Icon,
  actions,
  footer,
  getRowKey,
  onRowClick,
  testId = "data-table",
}) {
  return (
    <div className="section-card" data-testid={`${testId}-card`}>
      {(title || actions) && (
        <div className="section-head">
          <div className="flex min-w-0 items-center gap-2">
            {Icon ? <Icon size={16} className="text-[#007AFF]" /> : null}
            {title ? <h2 className="truncate">{title}</h2> : null}
          </div>
          {actions ? <div className="flex flex-wrap items-center justify-end gap-2">{actions}</div> : null}
        </div>
      )}
      <div className="overflow-x-auto">
        <Table data-testid={testId}>
          <TableHeader>
            <TableRow className="border-0 bg-[#FAFAFB] hover:bg-[#FAFAFB]">
              {columns.map((col) => (
                <TableHead
                  key={col.key}
                  className={cn(
                    "h-auto whitespace-nowrap py-3 text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]",
                    col.align === "right" && "text-right"
                  )}
                >
                  {col.label}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row, idx) => (
              <TableRow
                key={getRowKey ? getRowKey(row) : row.id || idx}
                className={cn("border-t border-[#F2F2F5] hover:bg-[#FAFAFB]", onRowClick && "cursor-pointer")}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                data-testid={`${testId}-row-${idx}`}
              >
                {columns.map((col) => {
                  // Sel tanpa `render` menampilkan teks MENTAH dari database. Satu nilai panjang
                  // yang tak wajar (mis. nama pelanggan 60.000 karakter — nyata, lihat BUG-0114)
                  // dulu melebarkan seluruh tabel sampai kolom lain terdorong keluar layar.
                  // Batas lebar + `truncate` menjaga tata letak apa pun isi datanya; nilai utuh
                  // tetap bisa dibaca lewat tooltip `title`.
                  const raw = col.render ? null : row[col.key] ?? "-";
                  const long = typeof raw === "string" && raw.length > 60;
                  return (
                    <TableCell
                      key={col.key}
                      title={long ? raw : undefined}
                      className={cn(
                        "whitespace-nowrap py-3 text-[13px] text-[#1F1F25]",
                        col.align === "right" && "text-right",
                        col.mono && "tabular-nums",
                        !col.render && "max-w-[320px] truncate"
                      )}
                    >
                      {col.render ? col.render(row) : raw}
                    </TableCell>
                  );
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {footer ? <div className="section-foot">{footer}</div> : null}
    </div>
  );
}
