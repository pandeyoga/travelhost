// vehicleTypes.js — SSOT tipe armada di frontend (kunci + label + kapasitas tipikal).
// Label SAMA dengan backend services/pricing.VEHICLE_TYPE_LABELS (dipakai invoice/PDF & WA).
// Dulu tiap layar punya daftar sendiri dan saling beda ("Isuzu Elf" vs "Elf / Microbus",
// "Medium Bus" vs "Bus Besar"), sehingga ERP, dokumen, dan situs menyebut unit berbeda.
export const VEHICLE_TYPES = [
  { k: "hiace_premio", l: "Hiace Premio", seats: 14 },
  { k: "hiace", l: "Hiace Commuter", seats: 14 },
  { k: "elf", l: "Elf / Microbus", seats: 19 },
  { k: "bus", l: "Bus Besar", seats: 29 },
  { k: "avanza", l: "Avanza / MPV", seats: 6 },
];

export const VEHICLE_TYPE_LABEL = Object.fromEntries(VEHICLE_TYPES.map((t) => [t.k, t.l]));
export const vtypeLabel = (k) => VEHICLE_TYPE_LABEL[k] || (k || "").replace(/_/g, " ");
// Bentuk {v, l} untuk Select/dropdown; withSeats menambah kapasitas, mis. "Hiace Premio (14)".
export const vehicleTypeOptions = ({ withSeats = false } = {}) =>
  VEHICLE_TYPES.map((t) => ({ v: t.k, k: t.k, l: withSeats ? `${t.l} (${t.seats})` : t.l }));
