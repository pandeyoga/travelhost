import { CalendarDays, Clock, MapPin, Star } from "lucide-react";

// LivePreviewPane — pratinjau langsung konten publik dari state form CMS.
// Mendukung resource 'destinations' & 'articles'. Membaca nilai form mentah
// (image/gallery = array, list/textarea = string) tanpa menyentuh API.
function asList(v) {
  if (Array.isArray(v)) return v;
  return String(v || "").split(/\n+/).map((s) => s.trim()).filter(Boolean);
}
function asHighlights(v) {
  let arr = v;
  if (typeof v === "string") {
    const s = v.trim();
    if (s.startsWith("[")) { try { arr = JSON.parse(s); } catch { arr = []; } }
    else arr = s.split(/\n+/);
  }
  if (!Array.isArray(arr)) return [];
  return arr.map((h) => (typeof h === "string" ? h : (h?.title || h?.label || ""))).filter(Boolean);
}
function galleryUrls(v) {
  return (Array.isArray(v) ? v : []).map((x) => (typeof x === "string" ? x : x?.url)).filter(Boolean);
}

function Frame({ children }) {
  return (
    <div className="sticky top-0">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-[#8E8E93]">Pratinjau Langsung</p>
      <div data-surface="public" data-theme="azure"
        className="overflow-hidden rounded-2xl border border-border bg-background" data-testid="live-preview">
        {children}
      </div>
    </div>
  );
}

export default function LivePreviewPanel({ resource, form = {} }) {
  if (resource === "articles") {
    const cover = form.cover_image;
    const highlights = asList(form.body).slice(0, 2);
    return (
      <Frame>
        <div className="relative h-32 bg-primary">
          {cover ? <div className="absolute inset-0 bg-cover bg-center" style={{ backgroundImage: `url('${cover}')` }} /> : null}
          <div className="absolute inset-0" style={{ background: "linear-gradient(180deg, rgba(8,14,32,0.1) 30%, rgba(8,14,32,0.85) 100%)" }} />
          <div className="absolute inset-x-0 bottom-0 p-3">
            {form.category ? <span className="rounded-full bg-accent/90 px-2 py-0.5 text-[10px] font-semibold uppercase text-accent-foreground">{form.category}</span> : null}
            <p className="mt-1 font-fraunces text-[17px] leading-tight text-white">{form.title || "Judul artikel"}</p>
          </div>
        </div>
        <div className="space-y-2 p-3">
          <p className="flex flex-wrap items-center gap-x-3 text-[11px] text-muted-foreground">
            <span className="inline-flex items-center gap-1"><CalendarDays size={12} /> Hari ini</span>
            {form.read_minutes ? <span className="inline-flex items-center gap-1"><Clock size={12} /> {form.read_minutes} mnt baca</span> : null}
            {form.author ? <span>· {form.author}</span> : null}
          </p>
          <p className="text-[12.5px] font-medium leading-relaxed text-foreground">{form.excerpt || "Ringkasan artikel akan tampil di sini."}</p>
          {highlights.map((p, i) => <p key={i} className="text-[11.5px] leading-relaxed text-muted-foreground line-clamp-2">{p}</p>)}
        </div>
      </Frame>
    );
  }

  // destinations (default)
  const hero = form.hero_image;
  const highlights = asHighlights(form.highlights).slice(0, 4);
  const gallery = galleryUrls(form.gallery).slice(0, 4);
  return (
    <Frame>
      <div className="relative h-32 bg-primary">
        {hero ? <div className="absolute inset-0 bg-cover bg-center" style={{ backgroundImage: `url('${hero}')` }} /> : null}
        <div className="absolute inset-0" style={{ background: "linear-gradient(180deg, rgba(8,14,32,0.05) 35%, rgba(8,14,32,0.85) 100%)" }} />
        {form.popular ? <span className="absolute left-3 top-3 rounded-full bg-accent/90 px-2 py-0.5 text-[10px] font-semibold text-accent-foreground">Populer</span> : null}
        <div className="absolute inset-x-0 bottom-0 p-3">
          <p className="font-fraunces text-[18px] text-white">{form.name || "Nama destinasi"}</p>
          <p className="mt-0.5 flex items-center gap-1 text-[11px] text-white/80"><MapPin size={12} /> {String(form.region || "-").replace(/_/g, " ")}</p>
        </div>
      </div>
      <div className="space-y-2 p-3">
        <p className="text-[12px] leading-relaxed text-muted-foreground line-clamp-3">{form.intro || form.description || "Deskripsi destinasi akan tampil di sini."}</p>
        {highlights.length ? (
          <div className="flex flex-wrap gap-1.5">
            {highlights.map((h, i) => <span key={i} className="inline-flex items-center gap-1 rounded-full bg-secondary px-2 py-0.5 text-[10.5px] text-foreground"><Star size={10} /> {h}</span>)}
          </div>
        ) : null}
        {gallery.length ? (
          <div className="grid grid-cols-4 gap-1">
            {gallery.map((u, i) => <span key={i} className="h-10 rounded-md bg-muted bg-cover bg-center" style={{ backgroundImage: `url('${u}')` }} />)}
          </div>
        ) : null}
      </div>
    </Frame>
  );
}
