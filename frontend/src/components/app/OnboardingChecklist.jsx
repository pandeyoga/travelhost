import { useState } from "react";
import { Link } from "react-router-dom";
import { Rocket, Check, X, ChevronRight, PartyPopper } from "lucide-react";
import { useResource } from "@/hooks/useResource";
import apiClient from "@/services/apiClient";
import { Progress } from "@/components/ui/progress";

/**
 * OnboardingChecklist — panduan mulai cepat per peran (Phase 8 / A5).
 * Status tugas diambil dari /api/onboarding (derived dari data nyata + manual).
 * Bisa di-dismiss; tersembunyi otomatis bila sudah di-dismiss.
 */
export default function OnboardingChecklist() {
  const { data, loading, reload } = useResource("/onboarding");
  const [busy, setBusy] = useState("");

  if (loading || !data || data.dismissed) return null;
  if (!data.tasks || data.tasks.length === 0) return null;  // tidak ada tugas → sembunyikan

  const pct = data.total ? Math.round((data.done / data.total) * 100) : 0;

  const markDone = async (key) => {
    setBusy(key);
    try {
      await apiClient.post("/onboarding/complete", { task: key });
      await reload();
    } finally {
      setBusy("");
    }
  };
  const dismiss = async () => {
    await apiClient.post("/onboarding/dismiss");
    await reload();
  };

  return (
    <div className="section-card" data-testid="onboarding-card"
      style={{ borderColor: "#D9E4FF", background: "linear-gradient(180deg,#F5F8FF,#FFFFFF)" }}>
      <div className="section-head" style={{ borderBottom: "none", paddingBottom: 0 }}>
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#007AFF]/12 text-[#007AFF]">
            {data.complete ? <PartyPopper size={18} /> : <Rocket size={18} />}
          </span>
          <div className="min-w-0">
            <h2 className="truncate text-[15px]">{data.complete ? "Mantap! Setup awal selesai" : "Mulai cepat — siapkan RahazaTrans"}</h2>
            <p className="text-[12px] text-[#6B6B73]">{data.done} dari {data.total} langkah selesai</p>
          </div>
        </div>
        <button onClick={dismiss} data-testid="onboarding-dismiss" title="Sembunyikan"
          className="shrink-0 rounded-md p-1.5 text-[#8E8E93] transition hover:bg-black/5 hover:text-[#1C1C1E]">
          <X size={16} />
        </button>
      </div>

      <div className="px-4 pt-2.5">
        <Progress value={pct} className="h-2 bg-[#007AFF]/15" />
      </div>

      <div className="grid gap-1.5 p-3 sm:grid-cols-2">
        {data.tasks.map((t) => (
          <div key={t.key} data-testid={`onboarding-task-${t.key}`}
            className="flex items-center gap-3 rounded-lg border border-[#E5E5EA] bg-white px-3 py-2.5">
            <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${t.done ? "bg-[#34C759] text-white" : "border-2 border-[#D1D1D6] text-transparent"}`}>
              <Check size={14} />
            </span>
            <div className="min-w-0 flex-1">
              <p className={`truncate text-[13px] font-semibold ${t.done ? "text-[#8E8E93] line-through" : "text-[#1C1C1E]"}`}>{t.label}</p>
              <p className="truncate text-[11.5px] text-[#8E8E93]">{t.desc}</p>
            </div>
            {!t.done ? (
              <div className="flex shrink-0 items-center gap-1">
                <Link to={t.link} data-testid={`onboarding-go-${t.key}`}
                  className="rounded-md bg-[#101935] px-2.5 py-1 text-[11.5px] font-semibold text-white transition hover:bg-[#1c2a52]">Buka</Link>
                <button onClick={() => markDone(t.key)} disabled={busy === t.key} title="Tandai selesai"
                  data-testid={`onboarding-done-${t.key}`}
                  className="rounded-md p-1 text-[#8E8E93] transition hover:text-[#34C759] disabled:opacity-50">
                  <Check size={16} />
                </button>
              </div>
            ) : (
              <ChevronRight size={16} className="shrink-0 text-[#C7C7CC]" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
