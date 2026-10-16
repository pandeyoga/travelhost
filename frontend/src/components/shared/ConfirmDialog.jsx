import { Loader2, AlertTriangle } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";

// Konfirmasi aksi destruktif (hapus). Memakai Dialog (konsisten dgn dialog lain di app).
export default function ConfirmDialog({
  open, onOpenChange, title = "Hapus data?", description,
  confirmLabel = "Hapus", busy = false, onConfirm, testId = "confirm-dialog",
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid={testId}>
        <DialogHeader>
          <div className="mb-1 flex h-11 w-11 items-center justify-center rounded-full bg-[#FFE0DC]">
            <AlertTriangle className="h-5 w-5 text-[#FF3B30]" aria-hidden="true" />
          </div>
          <DialogTitle>{title}</DialogTitle>
          {description ? <DialogDescription>{description}</DialogDescription> : null}
        </DialogHeader>
        <DialogFooter className="mt-2">
          <button className="secondary-button" onClick={() => onOpenChange(false)} data-testid={`${testId}-cancel`}>
            Batal
          </button>
          <button
            className="primary-button !bg-[#FF3B30] hover:!bg-[#E0352B]"
            style={{ boxShadow: "0 6px 16px rgba(255,59,48,0.22)" }}
            disabled={busy}
            onClick={onConfirm}
            data-testid={`${testId}-confirm`}
          >
            {busy ? <Loader2 size={14} className="animate-spin" /> : null} {confirmLabel}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
