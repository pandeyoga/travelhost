import MediaPickerDialog from "@/components/media/MediaPickerDialog";

/**
 * MediaLibrary.jsx — ADAPTER tipis ke pemilih media bersama (`components/media/MediaPickerDialog`).
 *
 * Kenapa berkas ini masih ada, bukan dihapus: editor halaman iklan memanggil komponen ini dari tiga
 * tempat (`LandingBuilder`, `MediaPicker`, `BlockFieldEditors`). Mempertahankan satu adapter membuat
 * penyatuan ke Media Manager v2 tidak menyentuh ketiga pemanggil sekaligus — perubahan besar yang
 * menyentuh banyak berkas justru memperbesar peluang satu di antaranya rusak tanpa terlihat.
 *
 * Isi lamanya (grid + panel detail versi sendiri) DIBUANG karena sudah menjadi bagian dari
 * `MediaBrowser`: dengan begitu editor iklan otomatis mendapat folder, unduh, ganti berkas, potong
 * gambar, dan pilih-banyak tanpa kode tambahan — dan tidak mungkin lagi "dua library" berbeda
 * perilaku pada aset yang sama.
 */
export default function MediaLibrary({
  open, onOpenChange, onPick, pickKind = "", multiple = false, title, description,
}) {
  return (
    <MediaPickerDialog open={open} onOpenChange={onOpenChange} onPick={onPick} pickKind={pickKind}
      multiple={multiple} title={title} description={description} />
  );
}
