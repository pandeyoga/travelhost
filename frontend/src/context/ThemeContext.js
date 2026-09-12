import { createContext, useCallback, useContext, useEffect, useState } from "react";
import apiClient from "@/services/apiClient";

// ThemeContext — kontrol tema PUBLIC (preset dari CMS/Pengaturan + mode light/dark).
// Preset disetel server (settings.theme_config); mode bisa di-toggle user & disimpan lokal.
// Hanya memengaruhi surface=public: .dark ditambahkan ke <html> saat provider aktif,
// dan DIBERSIHKAN saat unmount agar surface ERP tidak terdampak.
const PRESETS = ["azure", "midnight", "sunrise", "harbor"];
const MODE_KEY = "rahaza_theme_mode";
const PRESET_KEY = "rahaza_theme_preset";

const ThemeContext = createContext(null);

export function ThemeProvider({ children }) {
  const [preset, setPresetState] = useState(() => localStorage.getItem(PRESET_KEY) || "azure");
  const [mode, setMode] = useState(() => localStorage.getItem(MODE_KEY) || "light");
  const [ready, setReady] = useState(false);

  // Ambil konfigurasi tema dari server (sumber kebenaran untuk preset).
  useEffect(() => {
    let active = true;
    apiClient
      .get("/public/theme")
      .then((r) => {
        if (!active) return;
        const p = PRESETS.includes(r.data?.preset) ? r.data.preset : "azure";
        setPresetState(p);
        localStorage.setItem(PRESET_KEY, p);
        if (!localStorage.getItem(MODE_KEY) && (r.data?.mode === "dark" || r.data?.mode === "light")) {
          setMode(r.data.mode);
        }
      })
      .catch(() => {})
      .finally(() => active && setReady(true));
    return () => {
      active = false;
    };
  }, []);

  // Terapkan .dark + ATRIBUT SURFACE/PRESET pada <html> sesuai mode.
  //
  // Kenapa atributnya harus di <html>, bukan cukup di div layout: Radix mem-PORTAL konten
  // (DialogContent, SelectContent, Popover, Tooltip) ke `document.body` — DI LUAR div
  // `[data-surface="public"][data-theme=...]`. Tanpa atribut di <html>, seluruh permukaan
  // portal jatuh ke token :root (tema ERP terang) walau situs sedang dalam mode gelap:
  // dialog exit-intent & daftar opsi Select tampil terang di halaman gelap, dan pada kasus
  // terburuk warna teks vs latar berasal dari dua tema berbeda (temuan testing agent
  // iteration_86 — kelas bug yang sama dengan keluhan readability user).
  useEffect(() => {
    const root = document.documentElement;
    if (mode === "dark") root.classList.add("dark");
    else root.classList.remove("dark");
    root.setAttribute("data-surface", "public");
    root.setAttribute("data-theme", preset);
  }, [mode, preset]);

  // Bersihkan jejak tema public ketika meninggalkan surface public (provider unmount),
  // supaya konsol ERP tidak ikut memakai palet situs publik.
  useEffect(() => () => {
    const root = document.documentElement;
    root.classList.remove("dark");
    root.removeAttribute("data-surface");
    root.removeAttribute("data-theme");
  }, []);

  const toggleMode = useCallback(() => {
    setMode((m) => {
      const next = m === "dark" ? "light" : "dark";
      localStorage.setItem(MODE_KEY, next);
      return next;
    });
  }, []);

  const setPreset = useCallback((p) => {
    if (!PRESETS.includes(p)) return;
    setPresetState(p);
    localStorage.setItem(PRESET_KEY, p);
  }, []);

  return (
    <ThemeContext.Provider value={{ preset, mode, ready, toggleMode, setPreset, presets: PRESETS }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return (
    useContext(ThemeContext) || { preset: "azure", mode: "light", ready: true, toggleMode: () => {}, setPreset: () => {}, presets: PRESETS }
  );
}
