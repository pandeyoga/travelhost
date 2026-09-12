import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";

/**
 * SelectField — pembungkus tipis Select (shadcn/Radix) untuk menggantikan `<select>` native.
 *
 * Kenapa ada: `<select>` native tampil berbeda di setiap OS/browser (tinggi, font, panah,
 * daftar opsi memakai UI sistem) sehingga "kaku" dan tidak seragam dengan input lain
 * (docs/06_UIUX_STANDARDS.md; ditandai `ux_audit` W2). Membungkusnya di satu tempat mencegah
 * 4 pemakaian menuliskan ulang pola yang sama — termasuk 2 detail yang mudah salah:
 *
 *  1. Radix MELARANG `SelectItem` bernilai string kosong. Opsi "tanpa pilihan" karena itu
 *     dipetakan ke sentinel internal, lalu dikembalikan menjadi "" ke pemanggil — jadi
 *     kontrak state di halaman tidak berubah (tetap "" = tidak ada preferensi).
 *  2. Setiap opsi diberi `data-testid` deterministik `<testId>-opt-<slug>` agar otomasi UI
 *     bisa memilih tanpa bergantung teks label.
 */
const NONE = "__none__";

const slug = (v) =>
  String(v || "none")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "none";

export default function SelectField({
  value,
  onChange,
  options = [],
  testId,
  placeholder,
  className,
  contentClassName,
  disabled = false,
  ariaLabel,
}) {
  const current = value === "" || value === null || value === undefined ? NONE : String(value);

  return (
    <Select value={current} onValueChange={(v) => onChange(v === NONE ? "" : v)} disabled={disabled}>
      <SelectTrigger
        aria-label={ariaLabel || placeholder || testId}
        data-testid={testId}
        className={cn("h-9 rounded-lg border-[#E5E5EA] bg-white text-[13px] text-[#1C1C1E]", className)}
      >
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent className={contentClassName}>
        {options.map((o) => {
          const raw = o.value === "" || o.value === null || o.value === undefined ? NONE : String(o.value);
          return (
            <SelectItem key={raw} value={raw} className="text-[13px]" data-testid={`${testId}-opt-${slug(o.value)}`}>
              {o.label}
            </SelectItem>
          );
        })}
      </SelectContent>
    </Select>
  );
}
