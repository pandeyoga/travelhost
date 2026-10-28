/**
 * apiError.js — ubah `detail` galat API menjadi SATU kalimat Indonesia yang aman dirender.
 *
 * Kenapa perlu: FastAPI mengirim `detail` dalam tiga bentuk — string (HTTPException), array
 * Pydantic `[{type, loc, msg, ctx}]` (422), atau objek. Merender array/objek langsung sebagai
 * anak React membuat SELURUH halaman crash ("Objects are not valid as a React child"), dan `msg`
 * Pydantic berbahasa Inggris ("Input should be less than or equal to 60"). Helper ini selalu
 * mengembalikan string, dengan nama kolom (label UI bila diberikan) + aturan dalam bahasa Indonesia.
 */

const humanize = (name) => {
  const s = String(name).replace(/_/g, " ").trim();
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : "Isian";
};

/** Nama kolom dari `loc` Pydantic, mis. ["body", "signatures", 0, "title"] → "Judul kolom #1". */
function fieldName(loc, labels) {
  const parts = (Array.isArray(loc) ? loc : [loc]).filter((p) => p !== "body" && p !== "query" && p !== "path");
  const names = parts.filter((p) => typeof p === "string");
  const idx = parts.filter((p) => typeof p === "number");
  const last = names[names.length - 1];
  if (!last) return "Isian";
  const label = labels?.[names.join(".")] || labels?.[last] || humanize(last);
  return idx.length ? `${label} #${idx[idx.length - 1] + 1}` : label;
}

const listOf = (v) => String(v ?? "").replace(/'/g, "").replace(/ or /g, ", ");

/** Satu butir galat Pydantic → kalimat Indonesia. Tipe tak dikenal tetap memakai `msg` aslinya. */
function pydanticItem(item, labels) {
  const f = fieldName(item.loc, labels);
  const c = item.ctx || {};
  const msg = String(item.msg || "").replace(/^Value error, /, "").replace(/^Assertion failed, /, "");
  switch (item.type) {
    case "less_than_equal": return `${f} maksimal ${c.le}`;
    case "greater_than_equal": return `${f} minimal ${c.ge}`;
    case "less_than": return `${f} harus kurang dari ${c.lt}`;
    case "greater_than": return `${f} harus lebih dari ${c.gt}`;
    case "string_too_long": return `${f} maksimal ${c.max_length} karakter`;
    case "string_too_short": return Number(c.min_length) <= 1 ? `${f} wajib diisi` : `${f} minimal ${c.min_length} karakter`;
    case "too_long": return `${f} maksimal ${c.max_length} item`;
    case "too_short": return `${f} minimal ${c.min_length} item`;
    case "missing": return `${f} wajib diisi`;
    case "enum":
    case "literal_error": return `${f} harus salah satu dari: ${listOf(c.expected)}`;
    case "int_parsing":
    case "int_type":
    case "float_parsing":
    case "float_type":
    case "finite_number": return `${f} harus berupa angka`;
    case "int_from_float": return `${f} harus bilangan bulat`;
    case "bool_parsing":
    case "bool_type": return `${f} harus ya/tidak`;
    case "string_type": return `${f} harus berupa teks`;
    case "json_invalid": return "Format data yang dikirim tidak sah";
    default: return msg ? `${f}: ${msg}` : `${f} tidak sah`;
  }
}

/**
 * `detail` apa pun → string (kosong bila tak ada yang bisa dibaca).
 * @param {*} detail   string | array galat Pydantic | objek {message|msg|detail}
 * @param {Object} [labels]  peta nama kolom API → label UI, mis. { width: "Lebar digit" }
 */
export function apiErrorText(detail, labels) {
  if (detail == null) return "";
  if (typeof detail === "string") return detail.trim();
  if (Array.isArray(detail)) {
    const lines = detail.map((d) => (d && typeof d === "object" ? pydanticItem(d, labels) : String(d ?? "")))
      .filter(Boolean);
    return [...new Set(lines)].slice(0, 3).join("; ");
  }
  if (typeof detail === "object") {
    if (detail.type && detail.loc) return pydanticItem(detail, labels);
    return apiErrorText(detail.message ?? detail.msg ?? detail.detail ?? null, labels);
  }
  return String(detail);
}

/** Pesan galat dari exception axios — tidak pernah objek, tidak pernah "[object Object]". */
export function apiErrorMessage(e, fallback = "Terjadi kesalahan", labels) {
  return apiErrorText(e?.response?.data?.detail, labels) || fallback;
}
