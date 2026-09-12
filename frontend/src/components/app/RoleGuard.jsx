import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { isDenied, roleHome, useDeniedNotice } from "@/lib/accessControl";

/**
 * RoleGuard — penjaga akses per-route berbasis SSOT (ROLE_MENU_ALLOWLIST).
 *
 * Menutup O-1 (RBAC bocor): sebelumnya route /app/* hanya dijaga autentikasi,
 * sehingga peran mana pun bisa membuka modul apa pun via URL langsung (mis.
 * driver → /app/settings). Guard ini memakai sumber kebenaran yang SAMA dengan
 * sidebar (canAccess) agar konsisten dengan docs/05_NAVIGATION_MAP.md & backend
 * permissions_config.py (disinkronkan paksa oleh guardrail INV-RBAC-04).
 *
 * E28: perilaku penolakan (pesan + tujuan pengalihan) dipindah ke
 * `@/lib/accessControl` agar identik dengan guard terpusat di AppShell.
 */
export default function RoleGuard({ section, children }) {
  const { user, loading } = useAuth();
  const denied = isDenied(user, section);
  useDeniedNotice(denied, section);

  if (loading) return null; // ProtectedRoute sudah menampilkan loader
  if (denied) return <Navigate to={roleHome(user.role)} replace />;
  return children;
}
