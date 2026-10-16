import { useEffect, useRef } from "react";
import { toast } from "sonner";
import { canAccess } from "@/config/navigationConfig";

/**
 * accessControl.js — SSOT perilaku "akses ditolak" di frontend.
 *
 * Kenapa modul ini ada (pelajaran E28): penolakan RBAC dulu ditulis DUA KALI —
 * di `AppShell.jsx` (guard terpusat berbasis path) dan di `RoleGuard.jsx` (guard
 * per-route). Keduanya benar secara keamanan, tapi UX-nya melenceng: AppShell
 * mengeksekusi lebih dulu sehingga perbaikan yang hanya ditaruh di RoleGuard
 * (pesan "Akses ditolak" + arahkan ke beranda peran) TIDAK PERNAH terlihat.
 * Sekarang keduanya memakai helper yang sama → tak ada drift.
 */

// Beranda per peran: driver diarahkan ke ruang kerjanya (bukan Control Tower)
// supaya pengalihan terasa "membantu", bukan sekadar dilempar keluar.
export const ROLE_HOME = {
  driver: "/app/driver-workspace",
  ops_admin: "/app/dashboard",
  owner: "/app/dashboard",
};

export function roleHome(role) {
  return ROLE_HOME[role] || "/app/dashboard";
}

export function isDenied(user, section) {
  return !!(user && section && !canAccess(user.role, section));
}

/** Beri tahu SEKALI per penolakan (hindari toast bertumpuk saat re-render). */
export function useDeniedNotice(denied, section) {
  const lastNotified = useRef(null);
  useEffect(() => {
    if (denied && lastNotified.current !== section) {
      lastNotified.current = section;
      toast.error("Akses ditolak", {
        description: "Modul ini tidak tersedia untuk peran akun Anda.",
      });
    }
    if (!denied) lastNotified.current = null;
  }, [denied, section]);
}
