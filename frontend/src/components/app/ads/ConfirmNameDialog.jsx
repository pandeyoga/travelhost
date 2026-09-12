import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";

/**
 * ConfirmNameDialog — pengaman untuk aksi yang MEMBELANJAKAN UANG (aktifkan iklan, terbitkan
 * kampanye, ubah budget). Tombol aksi baru hidup ketika nama objek diketik ulang PERSIS,
 * meniru pola "type to confirm" agar tidak ada aktivasi karena salah klik.
 */
export default function ConfirmNameDialog({
  open, expectedName, title, description, actionLabel, testId, onCancel, onConfirm,
}) {
  const [typed, setTyped] = useState("");
  useEffect(() => { if (open) setTyped(""); }, [open]);
  const matched = typed.trim() === (expectedName || "").trim() && Boolean(expectedName);

  return (
    <AlertDialog open={open} onOpenChange={(v) => { if (!v) onCancel?.(); }}>
      <AlertDialogContent data-testid={`${testId}-dialog`}>
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2">
            <AlertTriangle size={16} className="text-[#C25400]" /> {title}
          </AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-2">
          <p className="text-[12px] text-[#3a3f4a]">
            Ketik ulang: <b className="select-all">{expectedName || "(nama tidak diketahui)"}</b>
          </p>
          <input value={typed} onChange={(e) => setTyped(e.target.value)} data-testid={`${testId}-input`}
            placeholder="ketik nama objek di sini"
            className="h-9 w-full rounded-lg border border-[#E5E5EA] bg-white px-3 text-[13px] outline-none focus:border-[#007AFF]" />
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel data-testid={`${testId}-cancel`}>Batal</AlertDialogCancel>
          <AlertDialogAction disabled={!matched} data-testid={`${testId}-submit`}
            onClick={(e) => { if (!matched) { e.preventDefault(); return; } onConfirm?.(typed.trim()); }}>
            {actionLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
