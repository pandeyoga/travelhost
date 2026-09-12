import { Skeleton } from "@/components/ui/skeleton";
import { Inbox, AlertTriangle, RefreshCw } from "lucide-react";

export function LoadingState({ rows = 5, testId = "loading-state" }) {
  return (
    <div className="section-card" data-testid={testId}>
      <div className="section-body space-y-3">
        <Skeleton className="h-9 w-48 rounded-lg" />
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full rounded-lg" />
        ))}
      </div>
    </div>
  );
}

export function EmptyState({ title = "Belum ada data", description, action, testId = "empty-state" }) {
  return (
    <div
      className="flex flex-col items-center justify-center rounded-[14px] border border-dashed border-[#D9DADF] bg-white px-6 py-16 text-center"
      data-testid={testId}
    >
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[#F0F1F4]">
        <Inbox className="h-6 w-6 text-[#8E8E93]" aria-hidden="true" />
      </div>
      <h3 className="text-base font-bold text-[#1C1C1E]" style={{ fontFamily: "Outfit, sans-serif" }}>{title}</h3>
      {description ? <p className="mt-1 max-w-sm text-sm text-[#6B6B73]">{description}</p> : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

export function ErrorState({ message = "Terjadi kesalahan saat memuat data.", onRetry, testId = "error-state" }) {
  return (
    <div
      className="flex flex-col items-center justify-center rounded-[14px] border border-[#FFD0CC] bg-[#FFF5F4] px-6 py-16 text-center"
      data-testid={testId}
    >
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[#FFE0DC]">
        <AlertTriangle className="h-6 w-6 text-[#FF3B30]" aria-hidden="true" />
      </div>
      <h3 className="text-base font-bold text-[#1C1C1E]" style={{ fontFamily: "Outfit, sans-serif" }}>Gagal memuat</h3>
      <p className="mt-1 max-w-sm text-sm text-[#6B6B73]">{message}</p>
      {onRetry ? (
        <button className="secondary-button mt-5" onClick={onRetry} data-testid="error-retry-button">
          <RefreshCw size={14} /> Coba lagi
        </button>
      ) : null}
    </div>
  );
}
