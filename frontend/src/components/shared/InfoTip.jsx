import { Info } from "lucide-react";
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from "@/components/ui/tooltip";

/**
 * InfoTip — ikon info kecil dengan tooltip penjelas (in-app help, Phase 8 / A5).
 * Pemakaian: <InfoTip text="Penjelasan singkat" />
 */
export default function InfoTip({ text, size = 13, className = "" }) {
  if (!text) return null;
  return (
    <TooltipProvider delayDuration={120}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            tabIndex={-1}
            aria-label="Info"
            className={`inline-flex items-center text-[#B0B0B8] transition hover:text-[#007AFF] ${className}`}
            data-testid="info-tip"
          >
            <Info size={size} />
          </button>
        </TooltipTrigger>
        <TooltipContent className="max-w-[230px] bg-[#1C1C1E] text-[12px] leading-snug text-white">
          {text}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
