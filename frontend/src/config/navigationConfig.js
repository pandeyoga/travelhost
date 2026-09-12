// navigationConfig.js — IA grup collapsible (meniru Kain Nusantara).
import {
  LayoutDashboard,
  CalendarRange,
  CalendarDays,
  MapPin,
  Wrench,
  Bus,
  IdCard,
  Contact,
  MessageSquare,
  Wallet,
  BarChart3,
  UserCog,
  Settings,
  Truck,
  Database,
  LineChart,
  Cog,
  Inbox,
  ShieldCheck,
  Navigation,
  ClipboardCheck,
  FileText,
  Newspaper,
  LayoutTemplate,
  Images,
  Zap,
  Handshake,
  Megaphone,
  Activity,
  Plug,
} from "lucide-react";

// title = judul halaman; kicker = segmen breadcrumb (Beranda › kicker)
export const PAGE_META = {
  dashboard: { title: "Control Tower", kicker: "Eksekutif" },
  bookings: { title: "Booking & Trip", kicker: "Operasional" },
  calendar: { title: "Kalender Keberangkatan", kicker: "Operasional" },
  dispatch: { title: "Dispatch · Operasi Hari Ini", kicker: "Operasional" },
  "driver-workspace": { title: "Ruang Kerja Driver", kicker: "Operasional" },
  gps: { title: "GPS Tracking", kicker: "Operasional" },
  maintenance: { title: "Maintenance Armada", kicker: "Operasional" },
  partners: { title: "Pinjam Armada \u00b7 Sub-charter", kicker: "Operasional" },
  vehicles: { title: "Armada", kicker: "Master Data" },
  drivers: { title: "Driver", kicker: "Master Data" },
  customers: { title: "Customer 360", kicker: "Master Data" },
  masterdata: { title: "Referensi (Jemput & Destinasi)", kicker: "Master Data" },
  crm: { title: "CRM · Pipeline Lead", kicker: "CRM & Keuangan" },
  quotations: { title: "Penawaran · Quotation", kicker: "CRM & Keuangan" },
  inbox: { title: "Inbox · Percakapan", kicker: "CRM & Keuangan" },
  automation: { title: "Otomasi · Event & WhatsApp", kicker: "CRM & Keuangan" },
  finance: { title: "Keuangan", kicker: "CRM & Keuangan" },
  reports: { title: "Laporan", kicker: "CRM & Keuangan" },
  cms: { title: "Konten Web · CMS", kicker: "Konten Web" },
  media: { title: "Media Library", kicker: "Konten Web" },
  ads: { title: "Dashboard Iklan \u00b7 Biaya vs Booking", kicker: "Marketing" },
  landing: { title: "Landing Page Iklan", kicker: "Marketing" },
  tracking: { title: "Kesehatan Pelacakan", kicker: "Marketing" },
  integrations: { title: "Integrasi · API & Kredensial", kicker: "Marketing" },
  users: { title: "Manajemen User", kicker: "Sistem" },
  settings: { title: "Pengaturan", kicker: "Sistem" },
  documents: { title: "Dokumen · Invoice, Kwitansi & Penomoran", kicker: "Sistem" },
  auditlog: { title: "Jejak Audit", kicker: "Sistem" },
};

// Judul halaman per-TAB (dibaca Topbar dari query `?tab=`): heading mengikuti tab aktif
// supaya pengguna tidak bingung "di mana saya" saat berpindah tab dalam satu halaman.
export const PAGE_TAB_TITLES = {
  crm: {
    pipeline: "CRM · Pipeline Lead",
    scoreboard: "CRM · Skor & SLA",
    rfm: "CRM · RFM & LTV",
    segments: "CRM · Segmen Pelanggan",
    sequences: "CRM · Sequence Follow-up",
    campaigns: "CRM · Campaign",
    broadcast: "CRM · Broadcast WhatsApp",
    reminder: "CRM · Reminder Follow-up",
  },
};

// Struktur navigasi: standalone item + grup collapsible.
export const NAV_TREE = [
  { type: "standalone", id: "dashboard", label: "Beranda", icon: LayoutDashboard, path: "/app/dashboard" },
  {
    type: "group", groupId: "operasional", label: "Operasional", icon: Truck,
    items: [
      { id: "bookings", label: "Booking & Trip", icon: CalendarRange, path: "/app/bookings" },
      { id: "calendar", label: "Kalender Keberangkatan", icon: CalendarDays, path: "/app/calendar" },
      { id: "dispatch", label: "Dispatch", icon: Navigation, path: "/app/dispatch" },
      { id: "driver-workspace", label: "Ruang Kerja Driver", icon: ClipboardCheck, path: "/app/driver-workspace" },
      { id: "gps", label: "GPS Tracking", icon: MapPin, path: "/app/gps" },
      { id: "maintenance", label: "Maintenance", icon: Wrench, path: "/app/maintenance" },
      { id: "partners", label: "Pinjam Armada", icon: Handshake, path: "/app/partners" },
    ],
  },
  {
    type: "group", groupId: "master", label: "Master Data", icon: Database,
    items: [
      { id: "vehicles", label: "Armada", icon: Bus, path: "/app/vehicles" },
      { id: "drivers", label: "Driver", icon: IdCard, path: "/app/drivers" },
      { id: "customers", label: "Customer 360", icon: Contact, path: "/app/customers" },
      { id: "masterdata", label: "Referensi (Jemput & Destinasi)", icon: Database, path: "/app/masterdata" },
    ],
  },
  {
    type: "group", groupId: "crm-finance", label: "CRM & Keuangan", icon: LineChart,
    items: [
      { id: "crm", label: "CRM", icon: MessageSquare, path: "/app/crm" },
      { id: "quotations", label: "Penawaran", icon: FileText, path: "/app/quotations" },
      { id: "inbox", label: "Inbox", icon: Inbox, path: "/app/inbox" },
      { id: "automation", label: "Otomasi", icon: Zap, path: "/app/automation" },
      { id: "finance", label: "Keuangan", icon: Wallet, path: "/app/finance" },
      { id: "reports", label: "Laporan", icon: BarChart3, path: "/app/reports" },
    ],
  },
  {
    type: "group", groupId: "marketing", label: "Marketing & Iklan", icon: Megaphone,
    items: [
      { id: "ads", label: "Dashboard Iklan", icon: Megaphone, path: "/app/ads" },
      { id: "landing", label: "Landing Page Iklan", icon: LayoutTemplate, path: "/app/landing" },
      { id: "tracking", label: "Kesehatan Pelacakan", icon: Activity, path: "/app/tracking" },
      { id: "integrations", label: "Integrasi API", icon: Plug, path: "/app/integrations" },
    ],
  },
  {
    type: "group", groupId: "konten", label: "Konten Web", icon: Newspaper,
    items: [
      { id: "cms", label: "Halaman & Konten", icon: LayoutTemplate, path: "/app/cms" },
      { id: "media", label: "Media Library", icon: Images, path: "/app/media" },
    ],
  },
  {
    type: "group", groupId: "sistem", label: "Sistem", icon: Cog,
    items: [
      { id: "users", label: "Manajemen User", icon: UserCog, path: "/app/users" },
      { id: "settings", label: "Pengaturan", icon: Settings, path: "/app/settings" },
      { id: "documents", label: "Dokumen & Penomoran", icon: FileText, path: "/app/documents" },
      { id: "auditlog", label: "Jejak Audit", icon: ShieldCheck, path: "/app/auditlog" },
    ],
  },
];

export const ROLE_MENU_ALLOWLIST = {
  owner: ["dashboard", "bookings", "calendar", "dispatch", "driver-workspace", "gps", "maintenance", "partners", "vehicles", "drivers", "customers", "masterdata", "crm", "quotations", "inbox", "automation", "finance", "reports", "ads", "landing", "tracking", "integrations", "cms", "media", "users", "settings", "documents", "auditlog"],
  ops_admin: ["dashboard", "bookings", "calendar", "dispatch", "driver-workspace", "gps", "maintenance", "partners", "vehicles", "drivers", "customers", "masterdata", "crm", "quotations", "inbox", "automation", "finance", "reports", "ads", "cms", "media"],
  // FASE F (E29): peran BARU 'marketing_admin' — pemilik kanal akuisisi. Boleh mengelola
  // kredensial API iklan, landing page, kampanye, dan lead iklan; TIDAK boleh menyentuh
  // keuangan, pengaturan sistem, manajemen user, maupun operasional armada.
  // SSOT: docs/05_NAVIGATION_MAP.md §3 + backend/permissions_config.py (dipaksa INV-RBAC-04).
  marketing_admin: ["dashboard", "customers", "crm", "inbox", "ads", "landing", "tracking", "integrations", "cms", "media"],
  // RBAC-CAL-01: 'calendar' (Kalender Keberangkatan) DICABUT dari driver — halaman itu permukaan
  // manajemen (buat keberangkatan, setujui/tolak permintaan publik, tugaskan sopir, ekspor jadwal
  // seluruh armada), setara Dispatch yang juga ❌ untuk driver. SSOT: docs/05_NAVIGATION_MAP.md §3
  // + backend/permissions_config.py SECTION_ACCESS (disinkronkan paksa oleh INV-RBAC-04).
  driver: ["dashboard", "driver-workspace", "bookings", "gps", "maintenance", "vehicles", "drivers"],
};

export function navForRole(role) {
  const allow = new Set(ROLE_MENU_ALLOWLIST[role] || []);
  const out = [];
  for (const entry of NAV_TREE) {
    if (entry.type === "standalone") {
      if (allow.has(entry.id)) out.push(entry);
    } else if (entry.type === "group") {
      const items = entry.items.filter((i) => allow.has(i.id));
      if (items.length) out.push({ ...entry, items });
    }
  }
  return out;
}

export function canAccess(role, id) {
  return (ROLE_MENU_ALLOWLIST[role] || []).includes(id);
}
