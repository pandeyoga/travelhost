import { Star, Quote, ArrowRight, Clock, Plane } from "lucide-react";
import { formatCurrency } from "@/utils/formatters";
import { CardsSkeleton, EmptyNote, EntityCard, Heading, Wrap } from "@/components/app/landing/shared";

/**
 * blocks/EntityBlocks.jsx — blok yang menarik data NYATA dari ERP/CMS: armada, destinasi,
 * testimoni. Sebelumnya ketiganya hanya teks janji ("akan tampil otomatis…") sehingga halaman
 * iklan tampak kosong; padahal endpoint publiknya sudah ada sejak lama.
 *
 * Bentuk field mengikuti kontrak `/api/public/fleet` & `/api/public/destinations` yang
 * SUNGGUHAN (`photos[]`, `price_from`, `hero_image`) — renderer lama memakai `photo_url`/`day_rate`
 * yang tidak pernah ada, jadi gambar & harga selalu kosong tanpa error.
 */
/**
 * Utamakan unit yang LENGKAP (punya foto, dan harga bila harga ditampilkan). Halaman iklan tidak
 * boleh memamerkan kartu kosong: satu kartu tanpa foto/harga membuat seluruh halaman terasa tidak
 * terawat, padahal trafiknya dibayar. Kalau tak ada yang lengkap, tampilkan apa adanya daripada
 * kosong sama sekali.
 */
function preferComplete(rows, hasImage, needsPrice, hasPrice) {
  const complete = rows.filter((r) => hasImage(r) && (!needsPrice || hasPrice(r)));
  if (complete.length) return complete;
  const withImage = rows.filter(hasImage);
  return withImage.length ? withImage : rows;
}

function pickFleet(list, p) {
  let rows = Array.isArray(list) ? [...list] : [];
  if (p.ids?.length) rows = rows.filter((v) => p.ids.includes(v.id));
  if (p.vehicle_type) {
    const needle = String(p.vehicle_type).toLowerCase();
    const filtered = rows.filter((v) => String(v.type || "").toLowerCase().includes(needle));
    if (filtered.length) rows = filtered;
  }
  if (!p.ids?.length) {
    rows = preferComplete(rows, (v) => !!((v.photos && v.photos[0]) || v.hero_image),
      p.show_price !== false, (v) => !!v.price_from);
  }
  return rows.slice(0, p.limit || 6);
}

function pickDestinations(list, p) {
  let rows = Array.isArray(list) ? [...list] : [];
  if (p.ids?.length) rows = rows.filter((d) => p.ids.includes(d.id));
  if (p.region) {
    const needle = String(p.region).toLowerCase();
    const filtered = rows.filter((d) => String(d.region || "").toLowerCase().includes(needle));
    if (filtered.length) rows = filtered;
  }
  if (!p.ids?.length) {
    rows = preferComplete(rows, (d) => !!(d.hero_image || d.image_url),
      p.show_price !== false, () => false);
  }
  return rows.slice(0, p.limit || 6);
}

export function FleetGrid({ p, theme, fleet, loading, onCta }) {
  const rows = pickFleet(fleet, p);
  return (
    <Wrap theme={theme}>
      <Heading title={p.title} subtitle={p.subtitle} theme={theme} />
      {loading ? (
        <CardsSkeleton />
      ) : !rows.length ? (
        <EmptyNote testId="lp-fleet-empty">
          Belum ada armada yang bisa ditampilkan. Tambahkan unit di menu Armada.
        </EmptyNote>
      ) : (
        <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3" data-testid="lp-fleet-grid">
          {rows.map((v) => (
            <EntityCard key={v.id} theme={theme} testId={`lp-fleet-${v.id}`}
              onClick={() => onCta?.({ kind: "internal", target: `/fleet/${v.id}`, keep_attribution: true })}
              item={{
                name: v.name,
                meta: [v.capacity ? `${v.capacity} kursi` : "", String(v.type || "").replace(/_/g, " ")]
                  .filter(Boolean).join(" · "),
                priceNode: p.show_price && v.price_from
                  ? <span className="tabular-nums">Mulai {formatCurrency(v.price_from)}/hari</span>
                  : null,
                image: (v.photos && v.photos[0]) || v.hero_image || "",
              }} />
          ))}
        </div>
      )}
      {p.cta?.label ? (
        <div className="mt-4 text-center">
          <button type="button" onClick={() => onCta?.(p.cta)} data-testid="lp-fleet-cta"
            className="text-[13px] font-bold underline-offset-2 hover:underline" style={{ color: theme.primary }}>
            {p.cta.label}
          </button>
        </div>
      ) : null}
    </Wrap>
  );
}

export function DestinationGrid({ p, theme, destinations, loading, onCta }) {
  const rows = pickDestinations(destinations, p);
  return (
    <Wrap theme={theme}>
      <Heading title={p.title} subtitle={p.subtitle} theme={theme} />
      {loading ? (
        <CardsSkeleton />
      ) : !rows.length ? (
        <EmptyNote testId="lp-dest-empty">
          Belum ada destinasi yang bisa ditampilkan. Tambahkan di menu Konten &rarr; Destinasi.
        </EmptyNote>
      ) : (
        <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3" data-testid="lp-dest-grid">
          {rows.map((d) => (
            <EntityCard key={d.id} theme={theme} testId={`lp-dest-${d.id}`}
              onClick={() => onCta?.({ kind: "internal", target: `/destinations/${d.slug || d.id}`, keep_attribution: true })}
              item={{
                name: d.name,
                meta: [String(d.region || "").replace(/_/g, " "), d.duration || ""].filter(Boolean).join(" · "),
                // Destinasi TIDAK punya harga di model datanya (dulu blok ini merender
                // `d.price_from` yang tak pernah ada, jadi baris harga selalu kosong).
                priceNode: null,
                image: d.hero_image || d.image_url || "",
              }} />
          ))}
        </div>
      )}
    </Wrap>
  );
}

function durationLabel(minutes) {
  const m = Number(minutes) || 0;
  if (!m) return "";
  const h = Math.floor(m / 60);
  const r = m % 60;
  return `±${[h ? `${h} jam` : "", r ? `${r} mnt` : ""].filter(Boolean).join(" ")}`;
}

/**
 * RouteGrid — rute antar-jemput bertarif FLAT dari master ERP (`/api/public/booking/config`).
 * Tombol "Pesan rute ini" membuka wizard booking dengan layanan + rute SUDAH terpilih.
 */
export function RouteGrid({ p, theme, routes, loading, onCta }) {
  let rows = Array.isArray(routes) ? [...routes] : [];
  if (p.ids?.length) rows = rows.filter((r) => p.ids.includes(r.id));
  rows = rows.slice(0, p.limit || 6);
  return (
    <Wrap theme={theme}>
      <Heading title={p.title} subtitle={p.subtitle} theme={theme} />
      {loading ? (
        <CardsSkeleton />
      ) : !rows.length ? (
        <EmptyNote testId="lp-route-empty">
          Belum ada rute antar-jemput aktif. Tambahkan rute & tarif flat di menu pemesanan online.
        </EmptyNote>
      ) : (
        <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3" data-testid="lp-route-grid">
          {rows.map((r) => (
            <button key={r.id} type="button" data-testid={`lp-route-${r.id}`}
              onClick={() => onCta?.({ kind: "internal", label: `Pesan rute ${r.code || r.name}`,
                target: `/booking?service=airport_transfer&route=${r.id}`, keep_attribution: true })}
              className="group bg-white p-4 text-left shadow-sm transition-shadow hover:shadow-md"
              style={{ borderRadius: theme.radius }}>
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-full"
                style={{ background: `${theme.primary}15`, color: theme.primary }}>
                <Plane size={15} />
              </span>
              <h3 className="mt-2.5 flex items-center gap-1.5 text-[14px] font-bold leading-snug"
                style={{ color: theme.text }}>
                <span className="truncate">{r.from_label}</span>
                <ArrowRight size={13} className="shrink-0" style={{ color: theme.primary }} />
                <span className="truncate">{r.to_label}</span>
              </h3>
              <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11.5px] text-[#6B7280]">
                {r.code ? <span className="font-semibold uppercase tracking-wide">{r.code}</span> : null}
                {r.duration_minutes ? (
                  <span className="inline-flex items-center gap-1"><Clock size={11} /> {durationLabel(r.duration_minutes)}</span>
                ) : null}
              </div>
              {p.show_price !== false && r.from_price ? (
                <p className="mt-2 text-[14px] font-extrabold tabular-nums" style={{ color: theme.primary }}>
                  Mulai {formatCurrency(r.from_price)} <span className="text-[11px] font-semibold text-[#8B93A0]">flat / sekali jalan</span>
                </p>
              ) : null}
              <span className="mt-2.5 inline-flex items-center gap-1.5 text-[12.5px] font-bold"
                style={{ color: theme.primary }}>
                Pesan rute ini <ArrowRight size={12} className="transition-transform group-hover:translate-x-0.5" />
              </span>
            </button>
          ))}
        </div>
      )}
      {p.cta?.label ? (
        <div className="mt-4 text-center">
          <button type="button" onClick={() => onCta?.(p.cta)} data-testid="lp-route-cta"
            className="text-[13px] font-bold underline-offset-2 hover:underline" style={{ color: theme.primary }}>
            {p.cta.label}
          </button>
        </div>
      ) : null}
    </Wrap>
  );
}

export function Testimonials({ p, theme, testimonials, loading }) {
  let rows = Array.isArray(testimonials) ? [...testimonials] : [];
  if (p.ids?.length) rows = rows.filter((t) => p.ids.includes(t.id));
  rows = rows.slice(0, p.limit || 3);
  return (
    <Wrap theme={theme}>
      <Heading title={p.title} theme={theme} />
      {loading ? (
        <CardsSkeleton count={3} />
      ) : !rows.length ? (
        <EmptyNote testId="lp-testi-empty">
          Belum ada testimoni disetujui. Tambahkan di menu Konten &rarr; Testimoni.
        </EmptyNote>
      ) : (
        <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3" data-testid="lp-testimonials">
          {rows.map((t) => (
            <figure key={t.id} className="bg-white p-4 shadow-sm" style={{ borderRadius: theme.radius }}>
              <Quote size={16} style={{ color: theme.primary }} />
              <blockquote className="mt-2 text-[13px] leading-relaxed text-[#3C4350]">{t.quote}</blockquote>
              <div className="mt-3 flex items-center gap-2.5 border-t border-[#F0F1F3] pt-2.5">
                {t.avatar ? (
                  <img src={t.avatar} alt={t.name} loading="lazy" className="h-8 w-8 rounded-full object-cover" />
                ) : (
                  <span className="flex h-8 w-8 items-center justify-center rounded-full text-[11px] font-bold text-white"
                    style={{ background: theme.primary }}>{String(t.name || "?").slice(0, 1)}</span>
                )}
                <figcaption className="min-w-0">
                  <p className="truncate text-[12.5px] font-bold" style={{ color: theme.text }}>{t.name}</p>
                  {t.role ? <p className="truncate text-[11px] text-[#8B93A0]">{t.role}</p> : null}
                </figcaption>
                <span className="ml-auto flex shrink-0 items-center gap-0.5">
                  {Array.from({ length: Math.max(0, Math.min(5, t.rating || 5)) }).map((_, i) => (
                    <Star key={i} size={11} fill={theme.accent} stroke={theme.accent} />
                  ))}
                </span>
              </div>
            </figure>
          ))}
        </div>
      )}
    </Wrap>
  );
}
