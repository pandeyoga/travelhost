import { useState } from "react";
import { Outlet, useLocation, Navigate } from "react-router-dom";
import Sidebar from "@/components/app/Sidebar";
import Topbar from "@/components/app/Topbar";
import { useAuth } from "@/context/AuthContext";
import { isDenied, roleHome, useDeniedNotice } from "@/lib/accessControl";

export default function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { user } = useAuth();
  const location = useLocation();

  // A1: Guard RBAC terpusat — cegah render halaman terlarang saat diakses via URL langsung.
  // Sidebar sudah menyembunyikan menu per-role; ini melengkapi dengan redirect bersih
  // (konsisten untuk SEMUA halaman, menggantikan guard per-halaman yang tidak seragam).
  // E28: perilaku penolakan memakai SSOT `@/lib/accessControl` — sama dengan RoleGuard —
  // sehingga pesan "Akses ditolak" + tujuan pengalihan per peran tidak lagi berbeda
  // tergantung guard mana yang kebetulan dieksekusi lebih dulu.
  const pageId = location.pathname.replace(/^\/app\/?/, "").split("/")[0] || "dashboard";
  const denied = isDenied(user, pageId);
  useDeniedNotice(denied, pageId);
  if (denied) {
    return <Navigate to={roleHome(user.role)} replace />;
  }

  return (
    <div className="app-shell" data-surface="app">
      <div className="layout-grid">
        <Sidebar
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
          onNavigate={() => setMobileOpen(false)}
        />
        <div className="app-main">
          <Topbar onToggleSidebar={() => setMobileOpen((v) => !v)} />
          <main className="flex-1 px-4 py-5 md:px-7 md:py-6">
            <div className="mx-auto w-full max-w-[1400px]">
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
