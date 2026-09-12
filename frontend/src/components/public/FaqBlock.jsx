import SectionHeading from "@/components/public/SectionHeading";
import GlassCard from "@/components/public/GlassCard";
import {
  Accordion, AccordionItem, AccordionTrigger, AccordionContent,
} from "@/components/ui/accordion";
import { useLangValue } from "@/hooks/useLang";
import { bi } from "@/lib/i18n";

// FaqBlock.jsx — blok FAQ yang bisa dipakai ulang di halaman publik mana pun.
// Dibuat komponen supaya jawaban yang menyebut ANGKA KEBIJAKAN (DP, lama hold) selalu
// berasal dari satu tempat pemanggil (data server), bukan diketik ulang per halaman.
export default function FaqBlock({
  items,
  loading = false,
  eyebrow,
  title,
  subtitle,
  testId = "faq-block",
  center = true,
}) {
  const lang = useLangValue();
  const rows = Array.isArray(items) ? items.filter((x) => x && x.q && x.a) : [];
  const eb = eyebrow || "FAQ";
  const ttl = title || bi("Pertanyaan yang sering diajukan", "Frequently asked questions", lang);

  return (
    <section className="mx-auto max-w-3xl px-4 py-16 sm:px-6 lg:px-8" data-testid={testId}>
      <SectionHeading center={center} eyebrow={eb} title={ttl} subtitle={subtitle} />
      {loading ? (
        <div className="mt-8 space-y-3" data-testid={`${testId}-loading`}>
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-14 animate-pulse rounded-xl bg-muted" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <p className="mt-8 rounded-2xl border border-dashed border-border bg-card px-5 py-10 text-center text-[13.5px] text-muted-foreground" data-testid={`${testId}-empty`}>
          {bi("Belum ada pertanyaan yang dirangkum untuk halaman ini.", "No questions have been compiled for this page yet.", lang)}
        </p>
      ) : (
        <GlassCard variant="premium" className="mt-8 px-6 py-2">
          <Accordion type="single" collapsible data-testid={`${testId}-accordion`}>
            {rows.map((f, i) => (
              <AccordionItem key={i} value={`${testId}-${i}`} className="border-b border-border last:border-b-0">
                <AccordionTrigger className="text-left text-[15px] font-medium text-foreground hover:no-underline" data-testid={`${testId}-q-${i}`}>
                  {f.q}
                </AccordionTrigger>
                <AccordionContent className="text-[13.5px] leading-relaxed text-muted-foreground" data-testid={`${testId}-a-${i}`}>
                  {f.a}
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </GlassCard>
      )}
    </section>
  );
}
